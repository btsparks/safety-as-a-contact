"""Scene analysis — run Claude Vision on cataloged photos.

Usage:
    python -m training.analyze [--limit N] [--skip-analyzed] [--delay SECONDS] [--model MODEL]
"""

import argparse
import base64
import io
import json
import logging
import sys
import time

import anthropic
from PIL import Image

from backend.config import settings
from training.db import TrainingSession, init_training_db
from training.models import PhotoCatalog, SceneAnalysis

# Claude Vision limit: 5MB base64. We resize images to stay under this.
MAX_BASE64_BYTES = 5_000_000  # leave headroom below 5,242,880
MAX_DIMENSION = 1568  # Anthropic recommended max

logger = logging.getLogger(__name__)

ANALYSIS_PROMPT = """\
Analyze this construction site photo. The image has metadata text overlays stamped \
on it (project name at top, photographer/GPS at bottom-left, date/time at bottom-right). \
Extract those overlays AND analyze the scene.

Return ONLY valid JSON with this exact structure:
{
  "scene_description": "1-2 sentence description of what's happening in the photo",
  "hazards_found": [
    {"hazard": "brief description", "severity": 1, "category": "environmental"}
  ],
  "trade_context": "what trade(s) appear to be working or what type of work is shown",
  "overall_severity": 1,
  "recommended_mode": "probe",
  "coaching_focus": "what a coaching response should focus on for this scene",
  "scene_tags": ["tag1", "tag2"],
  "metadata": {
    "project_name": "extracted from top text overlay or null",
    "photographer": "extracted from bottom-left overlay or null",
    "gps_lat": null,
    "gps_lon": null,
    "date_time": "extracted from bottom-right overlay or null"
  }
}

Rules for analysis:
- hazards_found: list of real hazards visible. Empty list [] if none visible.
- severity scale: 1=minor housekeeping, 2=low awareness item, 3=moderate needs attention, 4=serious immediate action, 5=life-threatening stop work
- recommended_mode: alert (severity 4-5 only), validate (worker expressed doubt), nudge (real non-critical hazard), probe (no obvious hazard but narrow focus), affirm (genuinely solid setup)
- scene_tags: useful descriptors like "excavation", "crane_operation", "concrete_work", "pipe_installation", "grating", "ppe_visible", "indoor", "outdoor", "elevated_work", "confined_space", etc.
- coaching_focus: What ONE thing should the coaching AI focus its response on? Be specific.
- For GPS coordinates, parse numbers from the overlay text (format like "40.74273, -112.126511"). Return as floats or null if not readable.
- category must be one of: environmental, equipment, procedural, ergonomic, behavioral

Return ONLY the JSON. No explanation, no markdown fences."""


def _load_and_resize(photo_path: str) -> str:
    """Load a photo and resize if needed to stay under the API limit.

    Returns base64-encoded JPEG string.
    """
    with open(photo_path, "rb") as f:
        raw = f.read()

    # Check if it's already small enough
    encoded = base64.b64encode(raw).decode("utf-8")
    if len(encoded) <= MAX_BASE64_BYTES:
        return encoded

    # Resize with Pillow
    img = Image.open(io.BytesIO(raw))
    img = img.convert("RGB")  # ensure no alpha channel

    # Scale down to max dimension
    w, h = img.size
    if max(w, h) > MAX_DIMENSION:
        ratio = MAX_DIMENSION / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

    # Encode as JPEG with decreasing quality until small enough
    for quality in (85, 75, 60, 45):
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        encoded = base64.b64encode(buf.getvalue()).decode("utf-8")
        if len(encoded) <= MAX_BASE64_BYTES:
            return encoded

    return encoded  # last attempt, even if still large


def analyze_photo(client: anthropic.Anthropic, photo_path: str, model: str) -> dict:
    """Run Claude Vision analysis on a single photo. Returns parsed result dict."""
    image_data = _load_and_resize(photo_path)

    start = time.monotonic()

    resp = client.messages.create(
        model=model,
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": image_data,
                    },
                },
                {"type": "text", "text": ANALYSIS_PROMPT},
            ],
        }],
    )

    latency = int((time.monotonic() - start) * 1000)
    raw_text = resp.content[0].text

    # Parse JSON from response (handle possible markdown fences)
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON in the response
        import re
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            result = json.loads(match.group())
        else:
            result = {"error": "Could not parse JSON", "raw": raw_text[:500]}

    result["_raw"] = raw_text
    result["_prompt_tokens"] = resp.usage.input_tokens
    result["_completion_tokens"] = resp.usage.output_tokens
    result["_latency_ms"] = latency
    result["_model"] = model

    return result


def run_analysis(
    limit: int | None = None,
    skip_analyzed: bool = True,
    delay: float = 0.3,
    model: str = "claude-haiku-4-5-20251001",
) -> dict:
    """Analyze photos and create SceneAnalysis rows.

    Returns summary stats dict.
    """
    if not settings.anthropic_api_key:
        print("Error: ANTHROPIC_API_KEY not set. Cannot run analysis.", file=sys.stderr)
        sys.exit(1)

    init_training_db()
    db = TrainingSession()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    # Get photos to analyze
    query = db.query(PhotoCatalog).filter(PhotoCatalog.is_pdf == False)

    if skip_analyzed:
        analyzed_ids = [
            r[0] for r in db.query(SceneAnalysis.photo_id).all()
        ]
        if analyzed_ids:
            query = query.filter(PhotoCatalog.id.notin_(analyzed_ids))

    query = query.order_by(PhotoCatalog.date_taken.asc())
    if limit:
        query = query.limit(limit)

    photos = query.all()
    total = len(photos)

    if total == 0:
        print("No photos to analyze (all done or none cataloged).")
        db.close()
        return {"analyzed": 0, "errors": 0, "total_hazards": 0}

    print(f"Analyzing {total} photos with {model}...")

    stats = {"analyzed": 0, "errors": 0, "total_hazards": 0, "total_cost_tokens": 0}

    for i, photo in enumerate(photos, 1):
        try:
            result = analyze_photo(client, photo.file_path, model)

            # Create SceneAnalysis row
            hazards = result.get("hazards_found", [])
            sa = SceneAnalysis(
                photo_id=photo.id,
                scene_description=result.get("scene_description", ""),
                hazards_found=json.dumps(hazards),
                trade_context=result.get("trade_context", ""),
                severity=result.get("overall_severity", 1),
                recommended_mode=result.get("recommended_mode", "probe"),
                coaching_focus=result.get("coaching_focus", ""),
                scene_tags=json.dumps(result.get("scene_tags", [])),
                raw_response=result.get("_raw", ""),
                model_used=result.get("_model", model),
                prompt_tokens=result.get("_prompt_tokens", 0),
                completion_tokens=result.get("_completion_tokens", 0),
                latency_ms=result.get("_latency_ms", 0),
            )
            db.add(sa)

            # Backfill photo metadata from the vision extraction
            meta = result.get("metadata", {})
            if meta.get("project_name"):
                photo.project_name = meta["project_name"]
                # Extract number from parentheses, e.g., "RTK SPD Pump Station (8553)"
                import re
                num_match = re.search(r"\((\d+)\)", meta["project_name"])
                if num_match:
                    photo.project_number = num_match.group(1)
            if meta.get("photographer"):
                photo.photographer = meta["photographer"]
            if meta.get("gps_lat") is not None:
                try:
                    photo.gps_lat = float(meta["gps_lat"])
                    photo.gps_lon = float(meta.get("gps_lon", 0))
                    photo.has_gps = True
                except (ValueError, TypeError):
                    pass

            db.commit()
            stats["analyzed"] += 1
            stats["total_hazards"] += len(hazards)
            stats["total_cost_tokens"] += result.get("_prompt_tokens", 0) + result.get("_completion_tokens", 0)

            # Progress
            hazard_str = f"{len(hazards)} hazard(s)" if hazards else "no hazards"
            mode = result.get("recommended_mode", "?")
            sev = result.get("overall_severity", "?")
            print(
                f"  [{i}/{total}] sev={sev} mode={mode} {hazard_str} "
                f"| {photo.file_name[:40]}..."
            )

        except Exception as e:
            stats["errors"] += 1
            print(f"  [{i}/{total}] ERROR: {e} | {photo.file_name[:40]}...", file=sys.stderr)
            db.rollback()

        # Rate limiting
        if i < total:
            time.sleep(delay)

    db.close()
    return stats


def main():
    parser = argparse.ArgumentParser(description="Analyze photos with Claude Vision")
    parser.add_argument("--limit", type=int, default=None, help="Max photos to analyze")
    parser.add_argument(
        "--no-skip", action="store_true",
        help="Re-analyze even if already done",
    )
    parser.add_argument("--delay", type=float, default=0.3, help="Seconds between API calls")
    parser.add_argument("--model", default="claude-haiku-4-5-20251001", help="Vision model")
    args = parser.parse_args()

    stats = run_analysis(
        limit=args.limit,
        skip_analyzed=not args.no_skip,
        delay=args.delay,
        model=args.model,
    )

    print(f"\nAnalysis complete:")
    print(f"  Analyzed:      {stats['analyzed']}")
    print(f"  Hazards found: {stats['total_hazards']}")
    print(f"  Errors:        {stats['errors']}")
    print(f"  Total tokens:  {stats['total_cost_tokens']:,}")


if __name__ == "__main__":
    main()
