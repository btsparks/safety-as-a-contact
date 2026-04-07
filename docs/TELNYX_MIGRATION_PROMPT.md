# Claude Code Prompt: Twilio → Telnyx Migration + A2P 10DLC Compliance

Copy everything below the line into Claude Code.

---

**Read these files fully before making any changes:**
1. `project/backend/sms/handler.py` — current Twilio webhook handler
2. `project/backend/sms/sender.py` — current Twilio outbound sender
3. `project/backend/sms/consent.py` — consent management (keep as-is)
4. `project/backend/sms/compliance.py` — sending window + rate limits (keep as-is)
5. `project/backend/config.py` — environment config with Twilio vars
6. `project/docs/SMS_PROVIDER_RESEARCH.md` — full research on Telnyx and A2P compliance
7. `project/site/src/pages/privacy.astro` — privacy policy page
8. `project/site/src/pages/consent.astro` — consent/opt-in form

We are migrating from Twilio to Telnyx for SMS delivery. This involves three things: swapping the SMS layer code, updating the landing page for A2P compliance, and preparing exact registration details for the 10DLC campaign.

---

## Part 1: Swap SMS Layer from Twilio to Telnyx

### 1A. Update `backend/config.py`

Replace the Twilio config variables with Telnyx equivalents:

```python
# REMOVE these:
twilio_account_sid: str = ""
twilio_auth_token: str = ""
twilio_phone_number: str = ""
twilio_messaging_service_sid: str = ""

# ADD these:
telnyx_api_key: str = ""
telnyx_phone_number: str = ""
telnyx_messaging_profile_id: str = ""
telnyx_public_key: str = ""  # For webhook signature verification
```

### 1B. Rewrite `backend/sms/sender.py`

Replace Twilio sending logic with Telnyx. The function signature and compliance checks stay identical — only the actual send mechanism changes.

**Key changes:**
- Replace `from twilio.rest import Client` with `import telnyx`
- Replace `client.messages.create()` with `telnyx.Message.create()`
- Replace `settings.twilio_account_sid` / `settings.twilio_auth_token` checks with `settings.telnyx_api_key`
- The `telnyx.Message.create()` call needs: `from_`, `to`, `text`, and `messaging_profile_id`
- Telnyx returns a message object with `.data.id` (equivalent to Twilio's SID)
- Rename all variables/comments from `twilio_sid` to `message_sid` (generic)

```python
# Telnyx send pattern:
import telnyx
telnyx.api_key = settings.telnyx_api_key

message = telnyx.Message.create(
    from_=settings.telnyx_phone_number,
    to=to_phone,
    text=body,
    messaging_profile_id=settings.telnyx_messaging_profile_id,
)
message_sid = message.data.id
```

### 1C. Rewrite `backend/sms/handler.py`

Replace the Twilio webhook endpoint with a Telnyx webhook endpoint. The core `handle_inbound_message()` function stays the same — only the webhook parsing and signature validation change.

**Telnyx webhook format (JSON, not form data):**
```python
@router.post("/inbound")
async def inbound_sms(request: Request, db: Session = Depends(get_db)):
    """Handle inbound SMS/MMS from Telnyx webhook."""
    body = await request.json()
    event_type = body.get("data", {}).get("event_type", "")

    if event_type != "message.received":
        return {"status": "ignored"}

    payload = body["data"]["payload"]
    phone = payload["from"]["phone_number"]     # E.164 format
    text = payload.get("text", "").strip()

    # Extract MMS media URLs
    media = payload.get("media", [])
    media_urls = [
        m["url"] for m in media
        if m.get("content_type", "").startswith("image/")
    ]

    # CRITICAL: Telnyx media URLs are TEMPORARY.
    # Download photos immediately and store locally/S3.
    # Replace media_urls with permanent local paths after download.
    stored_urls = []
    for url in media_urls:
        local_path = await _download_media(url)
        if local_path:
            stored_urls.append(local_path)

    message_id = payload.get("id", "")

    handle_inbound_message(db, phone, text, message_id, media_urls=stored_urls or None)
    return {"status": "ok"}
```

**Add a media download helper:**
```python
import httpx
import os
import uuid
from pathlib import Path

MEDIA_DIR = Path("media/observations")

async def _download_media(url: str) -> str | None:
    """Download MMS media from Telnyx temporary URL and save locally.

    Telnyx media URLs expire — must download immediately on webhook receipt.
    Returns local file path or None if download fails.
    """
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=15.0)
            resp.raise_for_status()
            # Determine extension from content-type
            ct = resp.headers.get("content-type", "image/jpeg")
            ext = "jpg" if "jpeg" in ct else ct.split("/")[-1]
            filename = f"{uuid.uuid4().hex}.{ext}"
            filepath = MEDIA_DIR / filename
            filepath.write_bytes(resp.content)
            return str(filepath)
    except Exception as e:
        logger.error("Failed to download media from %s: %s", url, e)
        return None
```

**Replace `extract_media_urls()` (Twilio-specific form parsing) with the JSON media extraction above.**

**Replace `_validate_twilio_signature()` with Telnyx webhook verification:**
```python
def _validate_telnyx_signature(request: Request, body: bytes) -> bool:
    """Validate Telnyx webhook signature."""
    if not settings.is_production:
        return True
    if not settings.telnyx_public_key:
        logger.warning("No Telnyx public key configured, skipping signature validation")
        return True

    # Telnyx uses ed25519 signature verification
    # The telnyx SDK handles this automatically when you set the public key
    import telnyx
    telnyx.public_key = settings.telnyx_public_key
    try:
        signature = request.headers.get("telnyx-signature-ed25519", "")
        timestamp = request.headers.get("telnyx-timestamp", "")
        telnyx.Webhook.construct_event(body.decode(), signature, timestamp)
        return True
    except Exception as e:
        logger.warning("Telnyx signature validation failed: %s", e)
        return False
```

### 1D. Update `requirements.txt`

```
# REMOVE:
twilio==9.3.0

# ADD:
telnyx>=2.1.0
httpx>=0.27.0   # (already present for testing, but confirm)
```

### 1E. Update `backend/models.py`

In the `MessageLog` table, the `twilio_sid` column should be renamed to `message_sid` since we're no longer using Twilio. However, to avoid a migration headache, just leave the column name as-is and use it to store the Telnyx message ID instead. Add a comment noting this.

### 1F. Update all tests

Search all test files for references to "twilio", "Twilio", "twilio_sid", "NumMedia", "MediaUrl", "MediaContentType", "X-Twilio-Signature", and update them for the Telnyx equivalents:
- Webhook payloads should use JSON body format (not form data)
- Media URLs should use the Telnyx `media` array format
- SID references should work with Telnyx message IDs
- Signature validation tests should use Telnyx headers

Run `pytest` after all changes — every test must pass.

---

## Part 2: Landing Page Updates for A2P 10DLC Compliance

### 2A. Update Privacy Policy (`site/src/pages/privacy.astro`)

**Change 1:** In the "Data Sharing" section under "Service providers", change:
```
Twilio (SMS delivery)
```
to:
```
Telnyx (SMS delivery)
```

**Change 2:** In the "SMS Communications" section, add this line at the end of the bullet list:
```
SMS opt-in data and consent status will not be shared with third parties for promotional or marketing purposes.
```
This exact language is required by TCR (The Campaign Registry) for 10DLC campaign approval.

### 2B. Update Consent Form (`site/src/pages/consent.astro`)

**Change 1:** The existing consent checkbox text is good but needs one addition. After the existing text, add:
```
SMS opt-in data and consent will not be shared with third parties.
```

**Change 2:** Make the phone number field description clearer by adding placeholder text or a note below it:
```
Your phone number will be used to send and receive safety coaching messages only.
```

### 2C. Rebuild the site

After making changes to the .astro files, rebuild the static site:
```bash
cd project/site && npm run build
```

Verify the changes appear in the built files under `site/dist/`.

---

## Part 3: 10DLC Campaign Registration Reference File

Create `project/docs/TELNYX_10DLC_REGISTRATION.md` — a reference document containing every detail Travis needs to register the brand and campaign on Telnyx. This must be character-perfect because 10DLC brand verification matches against IRS records exactly.

**Content for this file:**

```markdown
# Telnyx 10DLC Brand & Campaign Registration

## CRITICAL: Brand verification matches against IRS Form CP-575G exactly.
## Every character must match. "Street" vs "St." will cause permanent failure.

---

## Brand Registration Details

Enter these EXACTLY as shown (copied from IRS Notice CP575G dated March 12, 2026):

| Field | Value |
|-------|-------|
| **Legal Business Name** | SAFETY AS A CONTACT |
| **EIN / Tax ID** | 41-4833988 |
| **Street Address** | 2730 E STANFORD LN |
| **City** | HOLLADAY |
| **State** | UT |
| **ZIP** | 84117 |
| **Country** | US |
| **Entity Type** | Private_Profit |
| **Company Website** | https://safetyasacontact.com |
| **Vertical** | Construction |
| **Stock Exchange** | (leave blank — not publicly traded) |

**Name Control:** SPAR

**Notes:**
- Use ALL CAPS for business name and address exactly as shown on CP-575G
- Do NOT use "Holladay" — use "HOLLADAY"
- Do NOT use "2730 East Stanford Lane" — use "2730 E STANFORD LN"
- The IRS assigned this EIN on March 12, 2026
- Entity type is Private_Profit (LLC)

---

## Campaign Registration Details

| Field | Value |
|-------|-------|
| **Use Case** | Low Volume Mixed |
| **Sub Use Case** | Customer Care / Mixed |
| **Content Type** | Non-marketing — worker-initiated safety coaching |
| **Campaign Description** | (see below) |
| **Message Flow** | Worker-initiated. Workers text hazard observations and photos to a dedicated number. System responds with AI-powered coaching that references the company's uploaded safety documents. No unsolicited messages are ever sent. Double opt-in required: worker texts our number, receives confirmation prompt, replies YES to activate. |
| **Privacy Policy URL** | https://safetyasacontact.com/privacy |
| **Terms of Service URL** | https://safetyasacontact.com/terms |
| **Opt-in URL** | https://safetyasacontact.com/consent |
| **Opt-in Type** | Web form + SMS double opt-in |
| **Embedded Link** | No |
| **Embedded Phone** | No |
| **Number Pooling** | No |
| **Age-Gated Content** | No |
| **Direct Lending** | No |
| **Subscriber Opt-in** | Yes |
| **Subscriber Opt-out** | Yes |
| **Subscriber Help** | Yes |

### Campaign Description

> Safety as a Contact provides SMS-based workplace safety coaching for construction workers. Workers text photos and descriptions of jobsite hazard observations to a dedicated phone number. The system responds with AI-powered coaching that references the worker's company safety policies, site-specific safety plans, OSHA standards, and incident reports that have been uploaded by the company's safety director. Messages include safety document references with source attribution, behavioral reflection questions, and acknowledgments of worker observations. All messaging is worker-initiated — the system only sends messages in direct response to worker texts. No marketing, promotional, or unsolicited messages are ever sent. The program supports English and Spanish. Maximum message frequency is 5 per day during business hours (8 AM - 9 PM local time). Workers opt in via web form at safetyasacontact.com/consent or SMS double opt-in, and can opt out at any time by texting STOP.

### Sample Messages (submit all 5)

**Sample 1 — Document reference response (English):**
> Jake, your site safety plan covers fall protection for this type of work in Section 3.2. Who else on your crew has seen this area today?

**Sample 2 — Document reference response (Spanish):**
> Miguel, el plan de seguridad del sitio cubre protección contra caídas para este tipo de trabajo. ¿Quién más en tu equipo ha visto esta área hoy?

**Sample 3 — Reflective coaching response:**
> Got your photo — lot going on there. What caught your eye about this spot?

**Sample 4 — Opt-in confirmation:**
> Safety as a Contact: You're signed up for safety coaching via text. Send a photo of any jobsite observation and we'll respond with relevant safety info. Msg frequency varies, max 5/day. Reply HELP for help, STOP to cancel. Msg & data rates may apply.

**Sample 5 — Opt-out confirmation:**
> You've been unsubscribed from Safety as a Contact. You will not receive any more messages. Reply START to re-subscribe.

### Keywords

| Keyword | Response |
|---------|----------|
| **HELP** | Safety as a Contact: For support, email support@safetyasacontact.com or visit safetyasacontact.com. Reply STOP to opt out. Msg & data rates may apply. |
| **STOP** | You've been unsubscribed from Safety as a Contact. You will not receive any more messages. Reply START to re-subscribe. |
| **STOPALL** | (same as STOP) |
| **UNSUBSCRIBE** | (same as STOP) |
| **CANCEL** | (same as STOP) |
| **END** | (same as STOP) |
| **QUIT** | (same as STOP) |
| **START** | Safety as a Contact: Welcome back! Send a photo of any jobsite observation to get started. Msg frequency varies, max 5/day. Reply HELP for help, STOP to cancel. Msg & data rates may apply. |

---

## Post-Approval Checklist

After brand + campaign are approved:

- [ ] Purchase a local phone number in the Telnyx portal
- [ ] Associate the phone number with the approved campaign
- [ ] Set up the webhook URL: `https://[your-domain]/api/sms/inbound`
- [ ] Set webhook event type to `message.received`
- [ ] Configure the messaging profile with the campaign
- [ ] Set environment variables:
  - `TELNYX_API_KEY` — from Telnyx portal → API Keys
  - `TELNYX_PHONE_NUMBER` — the purchased number in E.164 format
  - `TELNYX_MESSAGING_PROFILE_ID` — from Messaging → Profiles
  - `TELNYX_PUBLIC_KEY` — from Telnyx portal (for webhook verification)
- [ ] Send a test message to yourself
- [ ] Reply to verify inbound webhook works
- [ ] Send a photo to verify MMS handling + photo download
- [ ] Text STOP to verify opt-out
- [ ] Text START to verify re-subscribe
- [ ] Text HELP to verify help response
```

---

## After All Changes

1. Run `pytest` — all tests must pass
2. Run `cd project/site && npm run build` to rebuild the landing page
3. Verify the privacy policy and consent form updates appear in `site/dist/`
4. Do NOT modify any coaching engine files, document retrieval, or worker profile code — this migration is SMS layer only
