# SMS Provider Research: Telnyx for Safety as a Contact

**Status:** Research complete — ready for implementation planning
**Last updated:** March 2026
**Context:** Replacing Twilio with Telnyx for A2P SMS delivery. Moving toward production SMS pipeline.

---

## Why Telnyx Over Twilio

Travis has already experienced the pain points with Twilio firsthand: unintuitive campaign registration, campaigns not passing approval, and high costs. Telnyx addresses all three.

**Pricing:** Telnyx is roughly half the cost of Twilio per message. SMS in the US is ~$0.004/message (both inbound and outbound) vs Twilio's $0.0079 outbound / $0.0075 inbound. MMS (which we need for photo receiving) is $0.02 outbound / $0.01 inbound. For a product where every worker interaction involves at least 2 messages (observation in + coaching response out), and many include MMS photos, this adds up fast across a company with 50-250 workers.

**10DLC Campaign Approvals:** Telnyx advertises 7x faster campaign approvals than industry average. They also offer zero-fee campaign migrations if you're moving from another provider. Given the difficulty Travis experienced getting Twilio campaigns approved, this is significant.

**Support:** All Telnyx customers get free 24/7 support from engineers. Twilio charges $1,500/month minimum for comparable support. For a startup product, this matters.

**Infrastructure:** Telnyx is a licensed carrier with direct network access — they don't go through third-party aggregators like Twilio does. This means fewer message delivery hops and potentially better reliability.

**10DLC Fee Transparency:** Telnyx passes through all 10DLC fees at cost with zero markup. They're explicit about this.

---

## Telnyx SMS Pricing Breakdown

### Per-Message Costs (US)
| Type | Outbound | Inbound |
|------|----------|---------|
| SMS | ~$0.004 | ~$0.004 |
| MMS | ~$0.020 | ~$0.010 |

### Phone Number Costs
- Local number: ~$1.00/month
- SMS/MMS capability add-on: $0.10/month per number

### 10DLC Registration Fees (passed through at cost from TCR)
| Fee | Amount | Frequency |
|-----|--------|-----------|
| Brand registration | One-time, included in setup | Once |
| Auth+ verification (if required) | $15 per attempt | Once |
| Campaign verification (manual vetting) | $15 | Per campaign |
| Campaign monthly — first 3 months | $30 upfront (standard use case) | One-time |
| Campaign monthly — after 3 months | $10/month (standard use case) | Monthly |

### Estimated Monthly Cost (Safety as a Contact)
Assuming 100 active workers, average 3 interactions/week per worker, each interaction = 1 MMS inbound + 1 SMS outbound:
- Inbound MMS: 100 × 3 × 4 weeks × $0.01 = **$12/month**
- Outbound SMS: 100 × 3 × 4 weeks × $0.004 = **$4.80/month**
- Phone number: **$1.10/month**
- 10DLC campaign: **$10/month**
- **Total: ~$28/month** for 100 workers

At Twilio rates, the same usage would be ~$45/month. The savings grow as you scale.

---

## A2P 10DLC Compliance — What We Need

### Registration Flow (in order)
1. **Create Telnyx account** and add a messaging profile
2. **Register Brand** — submit business identity to The Campaign Registry (TCR)
3. **Brand verification** — TCR validates against IRS records. Legal name, address, and EIN must match IRS Form CP-575 EXACTLY (even "Street" vs "St." causes permanent failure)
4. **Register Campaign** — describe the use case, provide sample messages, link to privacy policy and terms
5. **Campaign vetting** — manual review, $15 fee, typically 1-3 business days on Telnyx
6. **Associate phone number** to approved campaign
7. **Start sending**

### What We Already Have (A2P readiness audit)

The landing page built in a previous session already has most of the compliance infrastructure:

**Privacy Policy** (`/privacy`) — ✅ Complete
- Identifies who we are and what we do
- Lists all data collected (phone, name, observations, metadata)
- Explains how data is used
- SMS-specific section with data usage, frequency, opt-out instructions
- Explicit statement: "We do not sell, rent, or share your personal data with third parties for marketing purposes"
- Data retention policies
- Contact information

**SMS Terms** (`/sms-terms`) — ✅ Complete
- Program description
- Consent and opt-in mechanics (double opt-in via YES reply or web form)
- Message frequency disclosure (max 5/day during business hours)
- Opt-out keywords (STOP, STOPALL, UNSUBSCRIBE, CANCEL, END, QUIT)
- HELP instructions
- "Message and data rates may apply" disclosure
- Carrier disclaimer
- "Consent is not a condition of purchase or employment"
- Emergency disclaimer ("In an emergency, call 911")
- Supported languages (English and Spanish)

**Consent Form** (`/consent`) — ✅ Complete
- Collects company name, email, phone, crew size
- Phone number field is present (required for opt-in)
- Checkbox with explicit SMS consent language
- Links to Privacy Policy, Terms of Service, and SMS Terms
- "Safety as a Contact will not share your phone number with third parties"
- "Your consent is not a condition of purchase"

### What Needs to Be Added or Updated for Telnyx 10DLC

1. **Privacy policy update — third-party SMS data sharing clause:**
   TCR now requires explicit language stating: "SMS opt-in data and consent status will not be shared with third parties for promotional or marketing purposes." The current privacy policy says we don't share data for marketing, but it needs to specifically call out SMS opt-in data and consent status. One sentence addition.

2. **Service provider reference:**
   The privacy policy currently mentions "Twilio (SMS delivery)" under service providers. This needs to be updated to "Telnyx (SMS delivery)" when we switch.

3. **Campaign use case description:**
   When registering the 10DLC campaign with TCR, we'll need a clear use case description. This is NOT a marketing campaign — it's a "Low Volume Mixed" or "Customer Care" use case. Recommended description:

   > "Safety as a Contact provides SMS-based workplace safety coaching for construction workers. Workers text photos of jobsite hazard observations to a dedicated number and receive AI-powered coaching responses that reference their company's safety policies and procedures. Messages include coaching responses to worker observations, document references from uploaded safety plans, and behavioral reflection prompts. All messaging is worker-initiated — we do not send unsolicited marketing messages. Message frequency: up to 5 per day during business hours, only in response to worker activity. Supported languages: English and Spanish."

4. **Sample messages for campaign registration:**
   TCR requires 2-5 sample messages. These should match what the system actually sends:

   - "Jake, your site safety plan covers fall protection for this type of work in Section 3.2. Who else on your crew has seen this area today?"
   - "Got your photo. The Valar Ward 250 safety plan has a section on crane operations and rigging. Has this been covered in a toolbox talk?"
   - "Got your photo — lot going on there. What caught your eye about this spot?"
   - "Reply STOP to opt out at any time. Reply HELP for support. Msg & data rates may apply."

5. **Opt-in confirmation message template:**
   Required by TCR. Template:

   > "Safety as a Contact: You're signed up for safety coaching via text. Reply with a photo of any jobsite observation and we'll respond with relevant safety resources. Msg frequency varies, max 5/day. Reply HELP for help, STOP to cancel. Msg & data rates may apply."

---

## Technical Integration — How It Connects

### Architecture Overview

```
Worker Phone
    ↓ (SMS/MMS via carrier network)
Telnyx (receives message, sends webhook)
    ↓ (HTTPS POST to our server)
FastAPI Webhook Handler (new endpoint)
    ↓ (extracts text + photo URLs)
    ↓ → Downloads MMS photos from Telnyx URLs → stores in S3/local
    ↓ → Creates Observation record in database
    ↓ → Calls run_coaching() with observation text + photo
Coaching Engine
    ↓ → Retrieves documents from SafetyDocument table
    ↓ → Builds prompt with document context
    ↓ → Calls Claude Haiku API
    ↓ → Returns CoachingResult
FastAPI Webhook Handler
    ↓ (sends response back via Telnyx API)
Telnyx (delivers SMS to worker)
    ↓
Worker Phone (receives coaching response)
```

### Telnyx Python SDK

Install: `pip install telnyx`

**Sending a message:**
```python
import telnyx
telnyx.api_key = "YOUR_API_KEY"

telnyx.Message.create(
    from_="+15551234567",  # Your Telnyx number
    to="+15559876543",      # Worker's phone
    text="Got your photo. The site safety plan covers this in Section 3.2.",
    messaging_profile_id="your-profile-id",
)
```

**Receiving via webhook (Flask/FastAPI):**
```python
@app.post("/webhooks/telnyx")
async def telnyx_webhook(request: Request):
    body = await request.json()
    event_type = body["data"]["event_type"]

    if event_type == "message.received":
        payload = body["data"]["payload"]
        from_number = payload["from"]["phone_number"]
        text = payload.get("text", "")
        media = payload.get("media", [])  # MMS attachments

        # media[0]["url"] = temporary URL to download photo
        # media[0]["content_type"] = "image/jpeg"

        # Process observation...
        # Send coaching response...
```

**Key difference from Twilio:** Telnyx MMS media URLs are temporary. You MUST download photos immediately in the webhook handler and store them yourself (S3, local storage, etc.). Don't save the Telnyx URL as a permanent reference.

### Telnyx MCP Server (for development)

Telnyx offers an official MCP server that works with Claude Desktop, Claude Code, Cursor, etc. This lets you manage phone numbers, send test messages, and check delivery status directly from your AI coding tools without writing scripts.

They also have 175 "Agent Skills" for Claude Code covering their full API surface in Python. These are open source and free.

**Installation for Claude Code:**
The Telnyx MCP server can be installed locally and connected to Claude Desktop or Claude Code for development and testing.

### What Changes in the Codebase

The current codebase references Twilio in `backend/sms/`. For the Telnyx switch:

1. **Replace `twilio` dependency with `telnyx`** in requirements.txt
2. **Rewrite SMS handler** — `backend/sms/handler.py` needs to accept Telnyx webhook format instead of Twilio's
3. **Rewrite SMS sender** — `backend/sms/sender.py` needs to use `telnyx.Message.create()` instead of Twilio's client
4. **Update webhook signature validation** — Telnyx uses a different verification method than Twilio
5. **Add MMS photo download step** — Telnyx media URLs are ephemeral; download and store photos on receipt
6. **Update config** — Replace `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` with `TELNYX_API_KEY` / `TELNYX_MESSAGING_PROFILE_ID`
7. **Update privacy policy** — Change "Twilio" to "Telnyx" in service providers section

The coaching engine, document retrieval, worker profiles, and everything else stay untouched. The SMS layer is a clean boundary.

---

## 10DLC Campaign Registration Checklist

When ready to register (do this BEFORE writing any SMS code):

- [ ] Create Telnyx account at telnyx.com
- [ ] Set up a Messaging Profile in the Telnyx portal
- [ ] Register Brand with TCR:
  - Legal business name (must match IRS records exactly)
  - EIN / Tax ID
  - Business address (must match IRS Form CP-575)
  - Business type (Private/Profit for LLC)
  - Company website URL (safetyasacontact.com)
  - Vertical: "Construction"
- [ ] Wait for brand verification (1-3 business days)
- [ ] Update privacy policy with SMS opt-in data sharing clause
- [ ] Update service provider from "Twilio" to "Telnyx"
- [ ] Register Campaign:
  - Use case: "Low Volume Mixed" or "Customer Care"
  - Campaign description (see above)
  - Sample messages (see above)
  - Privacy policy URL: safetyasacontact.com/privacy
  - Terms URL: safetyasacontact.com/sms-terms
  - Opt-in method: Web form (safetyasacontact.com/consent) + SMS double opt-in
  - Message flow description: Worker-initiated. Workers text observations, system responds with coaching.
  - Help keyword: HELP
  - Opt-out keywords: STOP, STOPALL, UNSUBSCRIBE, CANCEL, END, QUIT
- [ ] Pay campaign verification fee ($15)
- [ ] Wait for campaign approval (1-3 business days on Telnyx)
- [ ] Purchase phone number and associate with approved campaign
- [ ] Send test messages to verify delivery

---

## Risks and Considerations

**Brand verification failure:** If the legal name/address/EIN don't match IRS records exactly, the brand stays permanently unverified. Get the IRS CP-575 form and match it character for character. This is the #1 cause of 10DLC registration failure across all providers.

**Campaign rejection:** Vague descriptions get rejected. The description above is specific and honest — "worker-initiated safety coaching" is a clear, non-marketing use case. If rejected, Telnyx support can help identify the issue (free support, unlike Twilio).

**Photo handling:** Telnyx media URLs expire. The webhook handler MUST download photos immediately. If the download fails or is delayed, the photo is gone. Build retry logic and consider a small queue.

**Rate limiting:** 10DLC campaigns have throughput limits based on trust score. A new brand starts with a lower trust score (~5 msg/second). For 100 workers this is fine. As the brand builds history, the trust score increases automatically.

**Existing Twilio code:** The current `backend/sms/` directory is built for Twilio. This is a clean swap — same webhook pattern, same send/receive logic, different SDK. Estimate: 1-2 hours of Claude Code work.

---

## Recommended Next Steps

1. **Create Telnyx account** and start brand registration immediately. This takes days for verification, so start now even if you're not ready to write code yet.
2. **Update privacy policy** with the SMS opt-in data sharing clause (one sentence).
3. **Update service provider** reference from Twilio to Telnyx.
4. **Once brand + campaign are approved**, give Claude Code the prompt to swap the SMS layer from Twilio to Telnyx.

The brand verification is the bottleneck. Everything else can happen in parallel.

---

*Research based on Telnyx documentation, pricing pages, and 10DLC compliance guides as of March 2026.*
