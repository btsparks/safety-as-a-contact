"""Document retrieval — query safety documents by trade, hazard category, keywords.

MVP uses SQLite LIKE queries / keyword matching. No vector embeddings.
"""

import json
import logging
from dataclasses import dataclass, field

from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.models import SafetyDocument

logger = logging.getLogger(__name__)

# ── Spanish → English safety term lookup ─────────────────────────────────
# Maps common Spanish construction safety terms to English equivalents so
# keyword retrieval works against English-language documents when workers
# send observations in Spanish.

ES_TO_EN_SAFETY_TERMS: dict[str, list[str]] = {
    # Hazards and conditions
    "caida": ["fall"],
    "caída": ["fall"],
    "andamio": ["scaffold"],
    "andamiaje": ["scaffolding"],
    "arnes": ["harness"],
    "arnés": ["harness"],
    "casco": ["hard hat", "helmet"],
    "guantes": ["gloves"],
    "lentes": ["glasses", "goggles"],
    "gafas": ["glasses", "goggles"],
    "chaleco": ["vest"],
    "botas": ["boots"],
    "barandilla": ["guardrail"],
    "baranda": ["guardrail"],
    "escalera": ["ladder"],
    "techo": ["roof"],
    "borde": ["edge"],
    "trinchera": ["trench"],
    "zanja": ["trench"],
    "excavacion": ["excavation"],
    "excavación": ["excavation"],
    # Tools and equipment
    "sierra": ["saw"],
    "taladro": ["drill"],
    "soldadura": ["welding"],
    "grua": ["crane"],
    "grúa": ["crane"],
    "montacargas": ["forklift"],
    "apuntalamiento": ["shoring"],
    "encofrado": ["formwork"],
    # Actions and conditions
    "peligro": ["danger", "hazard"],
    "riesgo": ["risk"],
    "resbalon": ["slip"],
    "resbalón": ["slip"],
    "tropiezo": ["trip"],
    "golpe": ["struck", "impact"],
    "atrapamiento": ["caught", "pinch"],
    "quemadura": ["burn"],
    "descarga": ["shock"],
    "electrocucion": ["electrocution"],
    "electrocución": ["electrocution"],
    "ruido": ["noise"],
    "polvo": ["dust"],
    "calor": ["heat"],
    "frio": ["cold"],
    "frío": ["cold"],
    "fuego": ["fire"],
    "explosion": ["explosion"],
    "explosión": ["explosion"],
    # PPE and procedures
    "proteccion": ["protection"],
    "protección": ["protection"],
    "seguridad": ["safety"],
    "herramienta": ["tool"],
    "equipo": ["equipment"],
    "guarda": ["guard"],
    "bloqueo": ["lockout"],
    "etiqueta": ["tagout"],
    "permiso": ["permit"],
    "inspeccion": ["inspection"],
    "inspección": ["inspection"],
    "senalizacion": ["signage"],
    "señalización": ["signage"],
    "limpieza": ["housekeeping", "cleanup"],
    "orden": ["housekeeping"],
    "escombros": ["debris"],
    "basura": ["trash"],
    # Body and ergonomics
    "espalda": ["back"],
    "levantamiento": ["lifting"],
    "peso": ["weight", "heavy"],
    "madera": ["lumber", "wood"],
    "concreto": ["concrete"],
    "acero": ["steel"],
    "clavo": ["nail"],
    "tornillo": ["bolt"],
    "tubo": ["pipe"],
    "tuberia": ["pipe"],
    "tubería": ["pipe"],
    "rebar": ["rebar"],
}

# Pre-built accent-stripped lookup for matching accented input
_ACCENT_MAP = str.maketrans("áéíóúñ", "aeionn")


def _strip_accents(word: str) -> str:
    """Strip common Spanish accents for lookup matching."""
    return word.translate(_ACCENT_MAP)


# Build a normalized lookup: accent-stripped key → list of English terms
_ES_NORMALIZED: dict[str, list[str]] = {}
for _es, _en_list in ES_TO_EN_SAFETY_TERMS.items():
    _norm = _strip_accents(_es.lower())
    if _norm not in _ES_NORMALIZED:
        _ES_NORMALIZED[_norm] = []
    for _en in _en_list:
        if _en not in _ES_NORMALIZED[_norm]:
            _ES_NORMALIZED[_norm].append(_en)


# Priority order for document categories — incident reports and lessons learned
# are most compelling to workers and should surface first when available.
CATEGORY_PRIORITY = [
    "incident_report",
    "lessons_learned",
    "hazard_register",
    "observation_insight",
    "site_safety_plan",
    "company_procedure",
    "osha_standard",
    "trade_reference",
]


@dataclass
class DocumentRetrievalResult:
    """Result from document retrieval — formatted for prompt injection."""
    formatted_context: str = ""
    document_ids: list[int] = field(default_factory=list)
    documents: list[dict] = field(default_factory=list)


def _extract_keywords(text: str) -> list[str]:
    """Extract meaningful keywords from observation text for matching.

    After extracting keywords, Spanish terms are looked up in
    ES_TO_EN_SAFETY_TERMS and their English equivalents are appended.
    This allows Spanish observations to match English-language documents.
    """
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "shall",
        "should", "may", "might", "must", "can", "could", "and", "but", "or",
        "nor", "not", "no", "so", "if", "then", "than", "too", "very", "just",
        "about", "above", "after", "again", "all", "also", "am", "any", "as",
        "at", "back", "because", "before", "between", "both", "by", "came",
        "come", "each", "from", "get", "got", "had", "he", "her", "here",
        "him", "his", "how", "in", "into", "it", "its", "like", "make",
        "many", "me", "my", "of", "on", "only", "other", "our", "out",
        "over", "re", "said", "she", "some", "still", "such", "take",
        "that", "their", "them", "these", "they", "this", "those", "to",
        "up", "us", "want", "we", "what", "when", "which", "while", "who",
        "with", "you", "your", "for",
        # Spanish stop words
        "el", "la", "los", "las", "un", "una", "de", "del", "en", "con",
        "por", "para", "que", "es", "hay", "ya", "no", "si", "se", "lo",
        "su", "más", "pero", "como", "sin", "sobre", "este", "esta",
        "esto", "ese", "esa", "eso", "mi", "tu", "mira",
        # Additional Spanish stop words
        "tiene", "tiene", "puesta", "dije", "está",
    }
    words = text.lower().split()
    # Keep words 3+ chars that aren't stop words
    base_keywords = [w.strip(".,!?()\"'") for w in words
                     if len(w) > 2 and w.strip(".,!?()\"'") not in stop_words]

    # Expand Spanish keywords with English equivalents
    expanded: list[str] = []
    seen: set[str] = set()
    for kw in base_keywords:
        if kw not in seen:
            expanded.append(kw)
            seen.add(kw)
        # Look up the accent-stripped form in the normalized table.
        # Also try stripping trailing 's' or 'es' for basic plural handling.
        norm = _strip_accents(kw)
        candidates = [norm]
        if norm.endswith("es") and len(norm) > 3:
            candidates.append(norm[:-2])
        if norm.endswith("s") and len(norm) > 3:
            candidates.append(norm[:-1])
        for candidate in candidates:
            en_terms = _ES_NORMALIZED.get(candidate, [])
            for en in en_terms:
                if en not in seen:
                    expanded.append(en)
                    seen.add(en)

    return expanded


def _sort_by_category_priority(docs: list[SafetyDocument]) -> list[SafetyDocument]:
    """Sort documents by category priority order."""
    priority_map = {cat: i for i, cat in enumerate(CATEGORY_PRIORITY)}
    return sorted(docs, key=lambda d: priority_map.get(d.category, 99))


def _format_document_snippet(doc: SafetyDocument) -> str:
    """Format a single document for prompt injection."""
    attribution = doc.source_attribution or doc.title
    section = f" — {doc.section_label}" if doc.section_label else ""
    content = doc.content
    # Truncate long content to ~500 chars for prompt budget
    if len(content) > 500:
        content = content[:497] + "..."
    return f"[Source: {attribution}{section}]\n{content}"


def retrieve_relevant_documents(
    db: Session,
    project_id: int | None,
    trade: str,
    observation_text: str,
    media_urls: list[str] | None = None,
    max_results: int = 3,
) -> DocumentRetrievalResult:
    """Query the document database for relevant safety document sections.

    Strategy (MVP — keyword matching, not vector):
    1. Filter by project_id (project-specific + global where project_id is null)
    2. Filter by trade_tags (include docs tagged for this trade + "all")
    3. Keyword match against observation_text
    4. Prioritize by category (incident_report > lessons_learned > hazard_register > ...)
    5. Return top N results formatted for prompt injection
    """
    keywords = _extract_keywords(observation_text)
    if not keywords:
        return DocumentRetrievalResult()

    # Build base query — project-specific + global documents
    project_filter = or_(
        SafetyDocument.project_id == project_id,
        SafetyDocument.project_id.is_(None),
    ) if project_id else SafetyDocument.project_id.is_(None)

    base_query = db.query(SafetyDocument).filter(project_filter)

    # Keyword matching — check content and title against observation keywords
    keyword_conditions = []
    for kw in keywords[:10]:  # limit to avoid huge queries
        keyword_conditions.append(SafetyDocument.content.ilike(f"%{kw}%"))
        keyword_conditions.append(SafetyDocument.title.ilike(f"%{kw}%"))

    if keyword_conditions:
        matching_docs = base_query.filter(or_(*keyword_conditions)).all()
    else:
        matching_docs = []

    if not matching_docs:
        return DocumentRetrievalResult()

    # Filter by trade relevance
    trade_relevant = []
    trade_lower = trade.lower()
    for doc in matching_docs:
        if not doc.trade_tags:
            trade_relevant.append(doc)  # No tags = applies to all trades
            continue
        try:
            tags = json.loads(doc.trade_tags)
            if "all" in tags or trade_lower in tags or not tags:
                trade_relevant.append(doc)
        except (json.JSONDecodeError, TypeError):
            trade_relevant.append(doc)  # Malformed tags = include

    # Use all matching docs if no trade-specific ones found
    docs_to_use = trade_relevant if trade_relevant else matching_docs

    # Sort by category priority and take top N
    sorted_docs = _sort_by_category_priority(docs_to_use)
    top_docs = sorted_docs[:max_results]

    # Format for prompt injection
    snippets = [_format_document_snippet(doc) for doc in top_docs]
    formatted = "\n\n".join(snippets)

    return DocumentRetrievalResult(
        formatted_context=formatted,
        document_ids=[doc.id for doc in top_docs],
        documents=[
            {
                "id": doc.id,
                "title": doc.title,
                "category": doc.category,
                "section_label": doc.section_label,
                "source_attribution": doc.source_attribution,
            }
            for doc in top_docs
        ],
    )
