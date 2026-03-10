# TWILIO A2P 10DLC — Expert Skill Reference

> **Purpose**: Guarantee first-attempt approval for Twilio A2P 10DLC campaign registration for the **Safety as a Contact** SMS-based construction safety coaching platform. This skill captures golden knowledge from 60+ sources including Twilio docs, CTIA guidelines, TCR requirements, real-world rejection case studies, and lessons from actual campaign submissions.

> **Product Context**: Safety as a Contact is an SMS-first behavioral coaching methodology for construction safety. Workers text a phone number to report hazards or request hazard identification help. AI responds with short, trade-aware, experience-calibrated coaching messages grounded in the company's own safety standards. The system also sends proactive shift-start coaching nudges and closes the feedback loop by connecting observations to toolbox talks. The product is white-labeled — each client company's branding, standards, and project details are integrated into AI responses.

---

## TABLE OF CONTENTS

1. [Campaign Approval Checklist](#1-campaign-approval-checklist)
2. [Rejection Error Codes & Fixes](#2-rejection-error-codes--fixes)
3. [Sample Messages — Rules & Templates](#3-sample-messages--rules--templates)
4. [Opt-In / Message Flow — Exact Requirements](#4-opt-in--message-flow--exact-requirements)
5. [Privacy Policy — Required Content](#5-privacy-policy--required-content)
6. [Terms of Service — Required Content](#6-terms-of-service--required-content)
7. [Brand Types Comparison](#7-brand-types-comparison)
8. [Campaign Use Cases](#8-campaign-use-cases)
9. [TCPA Compliance — Federal Law Layer](#9-tcpa-compliance--federal-law-layer)
10. [CTIA Compliance — Industry Regulatory Layer](#10-ctia-compliance--industry-regulatory-layer)
11. [Consent Management — Database & Flow](#11-consent-management--database--flow)
12. [Message Template Compliance](#12-message-template-compliance)
13. [Cost & Timeline](#13-cost--timeline)
14. [Post-Approval Setup](#14-post-approval-setup)
15. [Safety as a Contact — Specific Registration](#15-safety-as-a-contact--specific-registration)
16. [Lessons From Actual Submissions](#16-lessons-from-actual-submissions)
17. [Website Build Requirements](#17-website-build-requirements)
18. [Ongoing Compliance](#18-ongoing-compliance)

---

## 1. CAMPAIGN APPROVAL CHECKLIST

TCR (The Campaign Registry) and carrier reviewers evaluate every campaign against these criteria. **All must pass.**

### Mandatory Fields
| Field | Requirement |
|-------|------------|
| Campaign Description | 2-3+ sentences. WHO sends, WHO receives, WHY. Min 40 chars. |
| Sample Messages | Min 2, max 5. Fill all 5 for best odds. |
| Message Flow / CTA | Min 40 chars. Exact consent collection process. |
| Privacy Policy URL | Live, public, SMS-specific language. No login wall. |
| Terms & Conditions URL | Live, public, messaging terms. No login wall. |
| Opt-in Keywords | At least one (e.g., START, YES) |
| Opt-in Confirmation Message | Brand name + frequency + data rates + HELP/STOP |
| Content Checkboxes | Embedded links, phone numbers, lending, age-gated |

### Auto-Rejection Triggers
- Shortened URLs from free services (bit.ly, tinyurl) in sample messages
- SHAFT content (Sex, Hate, Alcohol, Firearms, Tobacco/marijuana)
- Privacy Policy or Terms URLs that return 404 or are behind a login
- Privacy Policy that does NOT mention SMS/mobile data collection
- Missing CTIA non-sharing clause in Privacy Policy
- Vague one-line campaign descriptions
- Sample messages that don't match the declared use case
- Sample messages missing brand name
- EIN/legal name mismatches with IRS records
- Registering as Sole Proprietor when you have an EIN (Error 30903)
- Generic email (gmail.com, yahoo.com) as support contact
- Website under construction or with placeholder content
- No visible SMS consent form or call-to-action on website

---

## 2. REJECTION ERROR CODES & FIXES

| Code | Name | Cause | Fix |
|------|------|-------|-----|
| **30880** | Unknown Error | Generic rejection | Contact Twilio support for specifics |
| **30881** | Invalid Brand Support Email | Email doesn't match or is invalid | Use domain-matching email (e.g., support@yourproduct.com) |
| **30882** | Terms & Conditions Issue | T&C page missing, inaccessible, or non-compliant | Ensure /terms is live, public, has all required sections |
| **30883** | Content Violation (SHAFT) | References sex, hate, alcohol, firearms, tobacco. **Cannot resubmit** | Contact support. Must create entirely new campaign |
| **30884** | Spam/Phishing | Campaign appears deceptive | Rewrite description and samples to be more specific and legitimate |
| **30885** | High Risk / Fraud | Deceptive marketing | Remove any misleading claims |
| **30890** | Subscriber Help Issue | HELP response inadequate | Include brand name, contact info, STOP instructions in HELP response |
| **30891** | Invalid Website URL | Site broken, under construction, or unbranded | Ensure site is live with business name, branding, content |
| **30892** | URL Shorteners | Sample messages contain bit.ly etc. | Use full URLs or branded short domains only |
| **30893** | Sample Mismatch | Samples don't match declared use case | Align samples with campaign description and use case |
| **30894** | Invalid Brand Info | Legal name/EIN/address mismatch with IRS | Match EXACTLY to IRS registration (no abbreviations) |
| **30897** | Disallowed Content | Violates carrier policies | Review content against CTIA guidelines |
| **30903** | Incorrect Sole Prop | Has EIN but registered as Sole Proprietor | Register as Standard or Low-Volume Standard brand |
| **30907** | Website URL Validation | URL doesn't match brand | Use business website domain consistently |
| **30908** | Privacy Policy Non-Compliant | Missing SMS privacy language | Add the CTIA non-sharing clause (see Section 5) |
| **30909** | CTA/Message Flow Incomplete | Opt-in process not adequately described | Detail EVERY consent touchpoint (see Section 4) |

### The 7 Most Common Real-World Rejections (ranked)
1. **Missing/non-compliant privacy policy** — no SMS non-sharing clause
2. **Inadequate message flow / CTA** — too vague on how consent is collected
3. **Sample message mismatches** — don't match use case or missing brand name
4. **Invalid website URL** — under construction, broken, no branding
5. **Business information mismatches** — legal name doesn't match IRS records exactly
6. **Generic email** — using gmail.com instead of business domain
7. **URL shorteners in samples** — bit.ly = instant rejection

---

## 3. SAMPLE MESSAGES — RULES & TEMPLATES

### Rules
- **Fill all 5 slots** — more samples = better context for reviewers
- **Every sample MUST include your brand/program name** (e.g., "Safety as a Contact:")
- **At least one sample MUST include opt-out language** ("Reply STOP to opt out")
- **Use brackets for variables**: `[Name]`, `[Project]`, `[Company]`
- **No public URL shorteners** (bit.ly, tinyurl = auto-reject)
- **No SHAFT content** references
- **Content must match your declared use case**
- **At least one sample should be the opt-in confirmation message**
- **Use realistic, concrete examples** — not generic templates. Reviewers need to see what actual messages look like.

### Safety as a Contact Sample Messages

**Sample 1 — Welcome/Opt-in Confirmation** (MUST have brand + frequency + rates + STOP/HELP):
```
Welcome to Safety as a Contact, sponsored by [Company Name]! You'll receive AI-powered safety coaching texts. Msg frequency varies (typically 1-5/day). Msg&data rates may apply. Reply YES to confirm. Reply HELP for help, STOP to cancel.
```

**Sample 2 — Proactive Shift-Start Nudge** (shows the outbound coaching feature):
```
Safety as a Contact: Good morning, Travis. You're on Building C today near the excavation. What's one thing you want to keep your eye on? Reply STOP to opt out.
```

**Sample 3 — AI Hazard Coaching Response** (shows the AI coaching feature):
```
Safety as a Contact: Good catch — that unprotected floor opening is a fall hazard per OSHA 1926.501(b)(1). Has the area been barricaded? Flag it for your foreman if not.
```

**Sample 4 — Feedback Loop Confirmation** (shows observation-to-action connection):
```
Safety as a Contact: Your observation about stairwell housekeeping on Building C became today's toolbox talk topic. Nice work keeping the crew aware.
```

**Sample 5 — Help Me Find a Hazard Response** (shows AI photo analysis):
```
Safety as a Contact: Based on your photo, I see 2 potential concerns: (1) Electrical cord across walkway — trip hazard (2) Missing barricade near open edge. Consider flagging both for your foreman.
```

### What Gets Rejected
- "Hello" — too generic, no brand
- "Welcome to our service! What's your name?" — no brand, sounds like generic chatbot
- "Check this: bit.ly/abc" — URL shortener
- "Saved! Observation #42. Reply 1 or 2." — missing brand name
- Marketing language ("BUY NOW!", "LIMITED TIME!") in non-marketing campaigns
- Generic templates with only bracket variables and no realistic content

---

## 4. OPT-IN / MESSAGE FLOW — EXACT REQUIREMENTS

The CTA/Message Flow field is the **second most common rejection point**. It must answer ALL of these:

### Required Elements
1. **WHERE** opt-in occurs (specific URL, in-person, text keyword)
2. **HOW** the user gives consent (checkbox, keyword text, verbal + first message)
3. **WHAT** they're told when consenting (exact disclosure language shown to them)
4. **CONFIRMATION** — what message they receive after opting in
5. **Links** to Privacy Policy and Terms of Service
6. **Opt-out** instructions (STOP keyword)

### Safety as a Contact Double Opt-In Flow Description

Use this exact template for the Message Flow / CTA field:

```
End users opt in through a two-step double opt-in process: (1) The worker
voluntarily sends an initial text message to our dedicated phone number,
which is provided to them by their employer's safety director during safety
orientations or posted on jobsite signage. This initial text constitutes
the first opt-in. (2) The system responds with a confirmation message that
includes the program name, sponsoring company name, message frequency,
data rate disclosure, and opt-out instructions, and asks the worker to
reply YES to confirm enrollment. Only after the worker replies YES are
they enrolled in the program and eligible to receive proactive coaching
messages. Consent records (phone number, timestamp, consent method) are
stored in our database. Additionally, our website at [URL] contains an
SMS enrollment page with an unchecked checkbox, full consent language,
and links to our Privacy Policy ([URL]/privacy) and Terms of Service
([URL]/terms). Workers can also enroll through this web form, which
triggers the same SMS double opt-in confirmation flow. Workers can opt
out at any time by replying STOP to any message.
```

### What Gets Rejected
- "Users opted in on our site" — too vague
- "Customers sign up" — no details on where/how
- "They text us first" — insufficient, no disclosure described
- No mention of Privacy Policy or Terms links
- No description of the confirmation message sent after opt-in
- No mention of how consent records are stored

---

## 5. PRIVACY POLICY — REQUIRED CONTENT

Your privacy policy page MUST contain ALL of the following sections. **The non-sharing clause is the #1 cause of campaign rejection when missing.**

### Section 1: SMS Data Collection
> We collect your name, mobile phone number, and consent to receive SMS messages when you text our dedicated phone number or submit the enrollment form on our website.

### Section 2: SMS Data Usage
> We use your mobile phone number to send AI-powered safety coaching messages, hazard identification assistance, shift-start safety awareness prompts, and observation feedback notifications related to your company's safety program.

### Section 3: THE CRITICAL NON-SHARING CLAUSE ⚠️
This exact language (or equivalent) is **mandatory per CTIA section 5.1.3**:

> **No mobile information will be shared with third parties/affiliates for marketing/promotional purposes. All the above categories exclude text messaging originator opt-in data and consent; this information will not be shared with any third parties.**

If your privacy policy mentions sharing data elsewhere for any reason, add:
> "All the above categories exclude text messaging originator opt-in data and consent; this information will not be shared with any third parties."

### Section 4: Data Security
> We employ industry-standard security measures to protect your information, including encrypted storage of consent records and phone numbers.

### Section 5: Data Retention & Deletion
> We retain consent and messaging records for a minimum of five years for legal compliance. You may request deletion of your personal information at any time by contacting us.

### Section 6: Opt-Out Instructions
> You can opt out at any time by replying STOP to any message from us. You may also text QUIT, END, REVOKE, OPT OUT, CANCEL, or UNSUBSCRIBE. Upon opting out, you will receive one final confirmation message and no further messages will be sent.

### Section 7: HELP Information
> For help, reply HELP to any message or contact us at [email] or [phone].

### Section 8: Message Frequency & Rates
> Message frequency varies based on your activity and company configuration, typically 1-5 messages per day. Message and data rates may apply. Contact your wireless carrier for details about your messaging plan.

### Section 9: Contact Information
> [Company name], [email], [phone], [physical address].

### Page Requirements
- Publicly accessible (no login required)
- On your business website domain
- Clearly labeled "Privacy Policy"
- Mobile-friendly and readable
- Linked from website footer/navigation
- Must be live BEFORE campaign submission

---

## 6. TERMS OF SERVICE — REQUIRED CONTENT

### Section 1: Program Name & Description
> The Safety as a Contact SMS Program is operated by [Legal Company Name]. This program sends AI-powered safety coaching messages, hazard identification assistance, shift-start awareness prompts, and observation feedback notifications to construction field workers who have enrolled in the program.

### Section 2: Message Types
List every category of message users may receive:
- Welcome/enrollment confirmation messages
- AI-powered hazard coaching responses
- Help-me-find-a-hazard photo analysis responses
- Proactive shift-start coaching nudges
- Observation feedback confirmations (when observations become toolbox talks)
- HELP and STOP response messages

### Section 3: Message Frequency
> Message frequency varies based on your activity and company configuration. Enrolled workers can expect to receive approximately 1-5 messages per day, including shift-start coaching prompts and responses to submitted observations.

### Section 4: Consent
> By opting in, you consent to receive recurring automated SMS messages from [Legal Company Name] through the Safety as a Contact program. Consent is not a condition of employment or any purchase.

### Section 5: Opt-Out (MUST be prominent/bold)
> **You can cancel at any time. Reply STOP to any message to unsubscribe. You will receive a one-time confirmation message. To rejoin, text START to our number.**

### Section 6: HELP
> Reply HELP for assistance, or contact us at [email] or [phone].

### Section 7: Data Rates
> Message and data rates may apply. [Legal Company Name] is not responsible for carrier charges.

### Section 8: Carrier Liability
> Carriers (T-Mobile, AT&T, Verizon, etc.) are not liable for delayed or undelivered messages.

### Section 9: Privacy Policy Link
> View our Privacy Policy at [URL]/privacy.

### Section 10: Contact Information
> [Company name], [phone], [email], [physical address].

---

## 7. BRAND TYPES COMPARISON

| Feature | Sole Proprietor | Low-Volume Standard | Standard |
|---------|----------------|-------------------|----------|
| Tax ID Required | No (SSN) | Yes (EIN) | Yes (EIN) |
| Brand Fee | $4.50 one-time | $4.50 one-time | $46.00 one-time |
| Campaigns Allowed | **1** | Multiple | Multiple (up to 5) |
| Phone Numbers/Campaign | **1** | Multiple | Multiple |
| Throughput | 1 MPS fixed | ~3-3.75 MPS | 4-225 MPS |
| T-Mobile Daily Cap | 1,000 msg/day | 2,000 msg/day | Up to 200,000+/day |
| Monthly Campaign Fee | $2/month | **$1.50/month** | $10/month |
| Use Cases | "Sole Proprietor" only | All standard | All standard |
| Secondary Vetting | No | No | Yes (included) |

### Decision Matrix for Safety as a Contact
- **SaaS product with EIN + scaling to multiple clients** → **Standard Brand** (higher throughput, multiple campaigns, trust score)
- **Has EIN + low volume initially (<6k msg/day)** → Low-Volume Standard as a starting point
- **No EIN / truly solo testing** → Sole Proprietor (but plan to upgrade)
- **Has EIN but registered as Sole Prop** → Error 30903 rejection risk (see Section 16)

### Recommended for Safety as a Contact: **Standard Brand**
As a SaaS product serving multiple construction companies, Standard Brand is the right choice:
- Allows multiple campaigns (one per white-label client if needed, or one shared campaign)
- Higher throughput scales with user base
- Secondary vetting builds trust score for better deliverability
- $46 one-time + $10/month is negligible relative to product pricing

---

## 8. CAMPAIGN USE CASES

| Use Case | Monthly Fee | Best For |
|----------|-----------|----------|
| 2FA | $1.50 | Login codes only |
| Account Notifications | $1.50 | Account status alerts |
| Customer Care | $1.50 | Support conversations |
| Delivery Notifications | $1.50 | Shipping alerts |
| Fraud Alert Messaging | $1.50 | Suspicious activity |
| Higher Education | $3.00 | Universities |
| **Low Volume Mixed** | **$1.50** | **Multiple message types, low volume** |
| Marketing | $10.00 | Promotional content |
| **Mixed** | **$10.00** | **Multiple types, high volume** |
| Polling and Voting | $1.50 | Non-political surveys |
| Public Service Announcement | $1.50 | Awareness campaigns |
| Security Alerts | $1.50 | System/physical security |
| Sole Proprietor | $2.00 | No EIN, single campaign |

### For Safety as a Contact
Use **Mixed** ($10/month) — covers all message types:
- AI-powered hazard coaching responses (worker-initiated)
- Photo analysis responses (worker-initiated)
- Proactive shift-start coaching nudges (system-initiated)
- Observation feedback confirmations (system-initiated)
- Welcome/enrollment/opt-in confirmation messages
- HELP/STOP/START keyword responses

Do NOT register as "Marketing" — our messages are operational/informational/coaching, not promotional. Do NOT try to fit into a narrow use case (like "Customer Care" or "Security Alerts") — mismatches cause rejection. Mixed is the safest choice for a multi-function application.

If volume is under 2,000 segments/day on T-Mobile initially, **Low Volume Mixed** ($1.50/month) is acceptable and saves cost. Upgrade to Mixed when volume increases.

---

## 9. TCPA COMPLIANCE — FEDERAL LAW LAYER

The Telephone Consumer Protection Act (47 U.S.C. § 227) is **federal law** with real financial penalties. This is not optional.

### Key Requirements
- **Prior express written consent** required before any automated messaging
- Penalties: **$500 per violation (negligent), $1,500 per violation (willful)** — per message
- Class action exposure is significant and growing
- **New one-to-one consent rule (effective January 26, 2026)**: Consent must be specific to the individual sender. Cannot rely on consent obtained by a lead generator or shared across multiple businesses. Each company using Safety as a Contact needs its own consent from workers.
- **Expanded opt-out methods (effective April 2025)**: Consumers can revoke consent via any reasonable means — reply text, email, voicemail, or informal language like "leave me alone" or "don't text me"
- **Time restrictions**: Messages only allowed **8am–9pm in the recipient's local time zone**
- **Caller ID**: Must identify the sender

### How This Applies to Safety as a Contact
- **Worker-initiated texts** (reporting a hazard, asking for help): The inbound message constitutes implied consent for the immediate response. TCPA risk is low for these interactions.
- **Proactive outbound messages** (shift-start coaching nudges, observation feedback confirmations): These are system-initiated and require **explicit prior written consent** through double opt-in. This is where TCPA liability exists.
- **White-label context**: Each client company is the "sender" under TCPA's one-to-one consent rule. Consent given for Company A's program does NOT cover Company B. If a worker switches employers, new consent is required.

### Required: TCPA Attorney Review
A TCPA compliance attorney **must** review the complete consent flow, message templates, opt-in/opt-out handling, and record retention before launch. This is non-negotiable. Schedule this for Week 5 of the implementation timeline.

---

## 10. CTIA COMPLIANCE — INDUSTRY REGULATORY LAYER

The CTIA Messaging Principles and Best Practices (May 2023) are enforced by carriers through TCR. Key requirements:

### Consent
- Explicit, campaign-specific opt-in required before any message
- Keep records of when, where, and how consent was captured
- NEVER purchase, rent, or share opt-in lists
- Confirmation message required after opt-in (brand + frequency + costs + opt-out)

### Opt-Out
- MUST support: STOP, UNSUBSCRIBE, CANCEL, END, QUIT
- MUST support: HELP keyword
- Honor opt-outs promptly (immediately, not "within 24 hours")
- Maintain clean lists (remove opted-out numbers immediately)

### Sender Identity
- Include brand/program name in message body
- Use branded domains (not public link shorteners)
- Phone numbers must connect to the identified business

### Message Timing
- Messages can only be sent **8am–9pm in recipient's local time**
- Sending outside this window flags your campaign for filtering

### Prohibited Content (SHAFT)
- Sex/sexual content
- Hate speech
- Alcohol
- Firearms
- Tobacco/Vape/Marijuana/CBD

Also prohibited: Cannabis, gambling, debt collection, payday loans, lead generation

### Recordkeeping
- Track complaint rates, bounces, opt-outs
- Remove deactivated numbers promptly
- Be prepared to provide consent proof if audited

---

## 11. CONSENT MANAGEMENT — DATABASE & FLOW

### 11.1 Database Schema for Consent Records

Build this table in the application database:

| Field | Type | Description | Required | Index |
|-------|------|-------------|----------|-------|
| id | UUID | Primary key | Yes | PK |
| phone_number | VARCHAR | E.164 format (+1xxxxxxxxxx) | Yes | Yes |
| consent_type | ENUM | sms_initial, sms_confirmed, web_form | Yes | Yes |
| consent_timestamp | DATETIME | When they first texted / submitted form (UTC) | Yes | — |
| consent_method | ENUM | inbound_sms, web_form, qr_code | Yes | — |
| consent_language | TEXT | Exact disclosure language shown to them | Yes | — |
| ip_address | VARCHAR | For web form submissions (nullable) | No | — |
| confirmation_timestamp | DATETIME | When they replied YES (UTC) | No | — |
| opt_out_timestamp | DATETIME | When they replied STOP (UTC) | No | — |
| opt_out_method | VARCHAR | STOP, email, verbal, etc. | No | — |
| worker_id | FK | Link to worker profile (nullable) | No | Yes |
| company_id | FK | Which client company | Yes | Yes |
| is_active | BOOLEAN | false if opted out | Yes | Yes |
| created_at | DATETIME | Record creation | Yes | — |
| updated_at | DATETIME | Last modification | Yes | — |

### 11.2 Consent Flow Implementation

Implement this exact technical flow:

1. **Worker texts the number** (or submits web form)
2. System receives inbound message via Twilio webhook
3. Check if phone_number exists in consent_records
4. **If new number**: Create consent_record with `consent_type=sms_initial`, `is_active=false`. Send confirmation message:
   > "Welcome to Safety as a Contact, sponsored by [Company Name]! You'll receive AI-powered safety coaching texts. Msg frequency varies (typically 1-5/day). Msg & data rates may apply. Reply YES to confirm enrollment. Reply STOP to cancel. Terms: [URL]/terms Privacy: [URL]/privacy"
5. **Worker replies YES**: Update consent_record → `consent_type=sms_confirmed`, `confirmation_timestamp=now()`, `is_active=true`. Send welcome message and begin profile onboarding.
6. **Worker replies STOP at any time**: Update `opt_out_timestamp=now()`, `is_active=false`. Send one final confirmation:
   > "You've been unsubscribed from Safety as a Contact. No more messages will be sent. Reply START to re-enroll."
7. **Worker replies HELP**: Return help information (no consent change):
   > "Safety as a Contact by [Company Name]. For support, contact [email] or call [phone]. Msg frequency varies. Msg & data rates may apply. Reply STOP to unsubscribe."
8. **NEVER send proactive messages** (shift-start nudges, feedback confirmations) to numbers where `is_active=false` or `consent_type != sms_confirmed`

### 11.3 Record Retention
- Consent records must be retained for **minimum 5 years** (TCPA statute of limitations is 4 years; 5 years provides buffer)
- **Never delete consent records** — soft delete only (set is_active=false)
- Must be retrievable for audits and legal discovery
- Include opt-out records (when and how they opted out) — this is your legal defense

---

## 12. MESSAGE TEMPLATE COMPLIANCE

Every outbound message must follow these rules:

### 12.1 First Message to New User (Double Opt-In Confirmation)
```
Welcome to Safety as a Contact, sponsored by [Company Name]! You'll
receive AI-powered safety coaching texts. Msg frequency varies
(typically 1-5/day). Msg & data rates may apply. Reply YES to confirm
enrollment. Reply STOP to cancel. Terms: [URL]/terms Privacy: [URL]/privacy
```

### 12.2 Post-Confirmation Welcome
```
Safety as a Contact: You're enrolled! I'm your safety coaching contact.
Text me anytime to report a hazard or send a photo for hazard ID help.
What trade are you in? (e.g., Electrical, Iron, Concrete, Mechanical)
```

### 12.3 Proactive Outbound Messages (Shift-Start Nudges)
**Requirements:**
- Must ONLY be sent to users with `consent_type=sms_confirmed` AND `is_active=true`
- Must be sent between **8am–9pm recipient's local time zone**
- Must include brand name
- First proactive message after enrollment should re-identify the program

```
Safety as a Contact: Good morning, [Name]. Today you're on [Project]
near the [work area]. What's one hazard you want to keep your eye on?
Reply STOP to opt out.
```

### 12.4 Inbound Response Messages (Hazard Coaching)
These respond to worker-initiated texts and are covered under implied consent. Still must be professional and consistent with the registered campaign description. Must include brand name.

```
Safety as a Contact: Good catch — [hazard description] is a concern per
[standard reference]. [Coaching question or suggestion]. Stay safe out there.
```

### 12.5 Feedback Loop Confirmations
System-initiated, requires confirmed consent. Include brand name.
```
Safety as a Contact: Your observation about [topic] on [project] became
this morning's toolbox talk topic. Your input is making a difference.
```

---

## 13. COST & TIMELINE

### One-Time Fees
| Item | Sole Prop | Low-Vol Standard | Standard |
|------|-----------|-----------------|----------|
| Brand Registration | $4.50 | $4.50 | $46.00 |
| Campaign Vetting | $15.00 | $15.00 | $15.00 |
| **Total** | **$19.50** | **$19.50** | **$61.00** |

### Monthly Recurring
- Sole Proprietor campaign: $2.00/month
- Low Volume Mixed campaign: $1.50/month
- Standard Mixed campaign: $10.00/month

### Per-Message Carrier Surcharges (on top of Twilio base ~$0.0079/segment)
| Carrier | Registered SMS | Registered MMS | Unregistered SMS |
|---------|---------------|----------------|-----------------|
| AT&T | $0.002 | $0.0035 | $0.01 |
| T-Mobile | $0.003 | $0.01 | $0.006 |
| Verizon | $0.0025 | $0.005 | $0.0025 |

### Projected Monthly Costs (per 100 active workers)
| Metric | Low Activity | Medium Activity | High Activity |
|--------|-------------|-----------------|---------------|
| Observations/worker/week | 1 | 3 | 5 |
| Messages per observation (in+out) | 2 | 3 | 4 |
| Proactive nudges/week | 5 | 5 | 5 |
| Total messages/month/worker | ~28 | ~62 | ~100 |
| SMS cost/month (100 workers) | ~$35 | ~$77 | ~$125 |
| AI API cost/month (100 workers) | ~$15 | ~$40 | ~$75 |
| Total variable cost/month | ~$50 | ~$117 | ~$200 |
| **Cost per worker/month** | **~$0.50** | **~$1.17** | **~$2.00** |

### Resubmission
- **3 free resubmissions** per rejected campaign (no additional vetting fee)
- Delete + recreate = $15 new vetting fee
- TCR allows only **5 total registration attempts** per campaign across all providers

### Timeline
- Brand approval: Minutes to a few days
- Campaign review: **10-15 business days** (sometimes longer)
- Carrier whitelisting after approval: Additional 2-5 days
- **Total: Budget 3-4 weeks** from submission to working SMS

### Implementation Timeline
| Week | Task | Status |
|------|------|--------|
| 1 | Verify business entity / EIN against IRS records | Pending |
| 1 | Build website with Privacy Policy, Terms, SMS consent page | Pending |
| 1 | Set up paid Twilio account | Pending |
| 1 | Purchase 10DLC phone number, create Messaging Service | Pending |
| 2 | Submit Brand Registration | Pending |
| 2 | Wait for brand approval + secondary vetting (1-5 days) | Pending |
| 2 | Build consent management database schema | Pending |
| 2 | Build Twilio webhook handlers (inbound/outbound) | Pending |
| 2-3 | Implement STOP/HELP/YES/START keyword handling | Pending |
| 2-3 | Submit Campaign Registration | Pending |
| 3-5 | Campaign under manual review (10-15 business days) | Pending |
| 3-5 | Build SMS coaching AI integration (parallel work) | Pending |
| 3-5 | Build consent record management in portal | Pending |
| 5 | Campaign approved — begin internal testing | Pending |
| 5 | TCPA attorney review of complete flow | Pending |
| 6 | Pilot with first company (5-10 workers) | Pending |

---

## 14. POST-APPROVAL SETUP

### When Campaign Status = VERIFIED
1. All 10DLC numbers in the Messaging Service are automatically registered for A2P
2. Carriers are notified to whitelist your numbers (2-5 days)
3. No further action needed for whitelisting

### Environment Variables
```
TWILIO_ACCOUNT_SID=<your SID>
TWILIO_AUTH_TOKEN=<your token>
TWILIO_PHONE_NUMBER=<your number in E.164 format, e.g., +13855551234>
TWILIO_MESSAGING_SERVICE_SID=<your messaging service SID>
```

### Webhook Configuration
- Set Messaging Service webhook URL to your `/api/sms/inbound` endpoint
- Enable "Defer to sender's webhook" in Messaging Service settings
- Ensure webhook accepts POST with Twilio's standard parameters
- Configure status callback URL for delivery status tracking at `/api/sms/status`

### Testing Checklist
1. Send inbound SMS → verify webhook receives request
2. Verify double opt-in flow (initial text → confirmation → YES → enrolled)
3. Test STOP keyword → should auto-unsubscribe and send confirmation
4. Test HELP keyword → should return help info with brand name and contact
5. Test START keyword → should re-subscribe and trigger new opt-in confirmation
6. Test YES keyword → should confirm enrollment
7. Test full hazard report flow (text description → AI coaching response)
8. Test full photo analysis flow (MMS photo → AI hazard identification)
9. Test proactive shift-start nudge delivery
10. Verify all outbound messages include brand name "Safety as a Contact"
11. Confirm 8am-9pm sending window is enforced (check against recipient timezone)
12. Verify consent records are created/updated correctly in database
13. Test with opted-out number → verify NO proactive messages are sent

---

## 15. SAFETY AS A CONTACT — SPECIFIC REGISTRATION

### Brand Strategy
Register a **Standard Brand** in Twilio Console using:
- Legal name: [Must match IRS exactly — verify against CP-575 letter]
- EIN: [Your EIN — must match IRS exactly]
- Business Industry: Software/Technology
- Company Type: Private
- Website: [Your live, SSL-secured URL]
- Support email: support@[yourdomain.com] (must match website domain)
- Use case: Mixed ($10.00/month) — or Low Volume Mixed ($1.50/month) if starting small

### Campaign Use Case
**Mixed** (or Low Volume Mixed for initial launch) — covers all message types:
- AI hazard coaching responses (worker-initiated)
- Photo-based hazard identification (worker-initiated)
- Shift-start coaching nudges (system-initiated / proactive)
- Observation feedback confirmations (system-initiated)
- Double opt-in enrollment flow
- Welcome and profile onboarding messages

### Recommended Campaign Description
```
Safety as a Contact is an SMS-based safety coaching program for
construction workers. Messages are sent by [Legal Company Name] to
construction field personnel who have voluntarily enrolled in the
program by texting our dedicated phone number. Workers receive:
(1) AI-powered safety coaching responses when they report a hazard
or request hazard identification assistance via text or photo,
(2) shift-start safety awareness prompts based on their trade,
project, and site conditions, and (3) confirmation messages when
their observations are incorporated into jobsite safety meetings.
All recipients have provided explicit prior consent through a
double opt-in process. Message frequency varies based on worker
activity, typically 1-5 messages per day. Recipients can opt out
at any time by replying STOP.
```

### Recommended Message Flow / CTA
```
End users opt in through a two-step double opt-in process: (1) The
worker voluntarily sends an initial text message to our dedicated
phone number, which is provided to them by their employer's safety
director during jobsite safety orientations or posted on jobsite
signage. During these orientations, the safety director explains
that the number is for reporting safety hazards and receiving
AI-powered safety coaching. This initial text constitutes the first
opt-in. (2) The system responds with a confirmation message that
includes the program name ("Safety as a Contact"), the sponsoring
company name, message frequency disclosure, data rate disclosure,
and opt-out instructions, and asks the worker to reply YES to
confirm enrollment. Only after the worker replies YES are they
enrolled in the program and eligible to receive proactive coaching
messages. Consent records (phone number, timestamp, consent method)
are stored in our database. Additionally, our website at [URL]
contains an SMS enrollment page with an unchecked checkbox, full
consent language, and links to our Privacy Policy ([URL]/privacy)
and Terms of Service ([URL]/terms). Workers can also enroll through
this web form, which triggers the same SMS double opt-in confirmation
flow. Workers can opt out at any time by replying STOP to any message.
Privacy Policy: [URL]/privacy. Terms: [URL]/terms.
```

### Content Checkboxes
- Messages will include embedded links: **Unchecked** (no URLs in messages)
- Messages will include phone numbers: **Unchecked**
- Messages include lending content: **Unchecked**
- Messages include age-gated content: **Unchecked**

### Pages Required Before Submission
1. `/privacy` — See Section 5 for all required content
2. `/terms` — See Section 6 for all required content
3. Homepage — clearly identifies the product, explains what it does
4. SMS enrollment section — visible consent form with unchecked checkbox
5. All pages must be live, public, SSL-secured, mobile-friendly, on the product domain

---

## 16. LESSONS FROM ACTUAL SUBMISSIONS

These findings are from actually completing campaign registrations end-to-end.

### Sole Proprietor with EIN — Didn't Auto-Reject
The skill warns about Error 30903 (Sole Prop with EIN). In practice, a submission as Sole Proprietor despite having an EIN was **accepted into review** — no immediate rejection. The 30903 error may only trigger during vetting review, not at submission time, or it may only apply when the EIN is actually registered on the brand profile (Sole Prop profiles don't collect EIN). **Still recommend Standard Brand when possible**, but Sole Prop isn't an automatic death sentence if Trust Hub blocks you.

### Trust Hub Console — Known Issues (as of March 2026)
Cannot create a Business Customer Profile via:
- **API**: Returns "This operation is restricted via API for Primary Customer Profiles"
- **Console**: Trust Hub > Customer Profiles page loads with completely blank content area
- **ISV path**: "ISV Starter Package registration has temporarily been disabled"

This means you **cannot upgrade from Sole Proprietor to Standard/LVS Brand** without Twilio support intervention. If Trust Hub is broken, use Sole Prop and monitor for 30903 rejection during review. **File a support ticket proactively** to request manual brand creation.

### Twilio Auto-Manages STOP/HELP Keywords
For Sole Proprietor campaigns, the registration form does **not** show fields for opt-out keywords, opt-out message, help keywords, or help message. The campaign detail page confirms: **"Twilio manages opt-out and help keywords for you by default."** These are handled at the Messaging Service level. You can customize them at Messaging Service > Opt-Out Management.

For Standard campaigns, you may have more control over these fields. Either way, implement your own STOP/HELP handling in webhook code as a backup layer.

### Confirmation Dialog After Clicking Create
After clicking "Create", a modal appears: **"Confirm Campaign registration"** with:
- Throughput limit information (varies by brand type)
- Agreement to allow Twilio to periodically migrate traffic to U.S. A2P routes
- Agreement to Twilio terms and conditions

Click "Confirm" to finalize submission.

### Messaging Service Conflicts
A Messaging Service can only be linked to **one A2P campaign at a time**. If you see "already associated with another A2P Campaign":
1. Navigate to Campaigns list
2. Find the conflicting campaign
3. Delete it (click the 3-dot menu > Delete, or open it and click "Delete Campaign")
4. Return to the registration form and re-select the messaging service

### Use Concrete Sample Messages
Instead of generic templates like `Observation #[ID] saved. Category: [Category]`, use **realistic examples** with actual values:
- "Safety as a Contact: Good catch — that unprotected floor opening is a fall hazard per OSHA 1926.501(b)(1). Has the area been barricaded?"
- "Safety as a Contact: Based on your photo, I see 2 potential concerns: (1) Electrical cord across walkway (2) Missing barricade near open edge."

This gives TCR reviewers clearer context about actual message content.

### Campaign Use Case Is Locked by Brand Type
With a Sole Proprietor brand, the "Available A2P Campaign use cases" dropdown is locked to **"Sole Proprietor"** only. You cannot select "Low Volume Mixed" or "Mixed" — those require a Standard or LVS brand.

### Actual Timeline Shown in Console
After submission, the campaign detail page states: **"may take 2-3 weeks to complete."** Twilio will email if there are issues. No A2P traffic allowed until status changes to VERIFIED.

---

## 17. WEBSITE BUILD REQUIREMENTS

The website must be built and live BEFORE campaign submission. TCR performs automated screenshot verification.

### Required Pages

**Homepage**
- Clearly identifies the product name ("Safety as a Contact")
- Explains what the product does (SMS-based safety coaching for construction)
- Professional design, not placeholder/coming soon
- SSL-secured (https://)
- Business contact information visible

**Privacy Policy Page** (`/privacy`)
- All content from Section 5
- Must include the CTIA non-sharing clause verbatim
- Must explicitly mention SMS/mobile data collection
- Must include opt-out instructions
- Must include message frequency and data rate disclosure
- Linked from footer on every page

**Terms of Service Page** (`/terms`)
- All content from Section 6
- Must include program name, message types, frequency, STOP, HELP, carrier disclaimer
- Must state "consent is not a condition of employment"
- Linked from footer on every page

**SMS Enrollment Section** (can be on homepage or dedicated `/enroll` page)
- Clear call-to-action for SMS enrollment
- **Unchecked checkbox** (CANNOT be pre-checked) with consent language:
  > ☐ I agree to receive SMS messages from Safety as a Contact (sponsored by [Company Name]). I understand I will receive safety coaching texts, typically 1-5 per day based on my activity. Message and data rates may apply. I can opt out at any time by replying STOP. [Privacy Policy] | [Terms of Service]
- Links to Privacy Policy and Terms of Service must be clickable
- Phone number field for enrollment
- Brand name visible

### Technical Requirements
- SSL certificate (https) — mandatory
- Mobile-responsive design
- Fast loading (screenshot bot has timeout)
- No login walls on Privacy Policy or Terms pages
- No URL shorteners used anywhere on the site
- Domain must match the business email domain used in brand registration

---

## 18. ONGOING COMPLIANCE

### Monthly Compliance Audit
- [ ] Verify all active numbers have valid consent records
- [ ] Check for STOP requests that may have been missed
- [ ] Review message delivery reports for carrier rejections (error 30007 = filtering)
- [ ] Ensure no messages sent outside 8am–9pm window
- [ ] Confirm privacy policy and terms of service are current on website
- [ ] Review carrier filtering rates (>5% = review message content)

### Carrier Filtering Monitoring
- Monitor Twilio delivery status callbacks for 30007 (carrier filtering) errors
- If filtering rates exceed 5%, review message content for spam-trigger patterns
- Avoid: ALL CAPS, excessive punctuation, URL shorteners, aggressive frequency
- Avoid sending identical messages to multiple recipients in rapid succession

### Legal Review Schedule
- **Pre-launch**: TCPA compliance attorney reviews complete flow (non-negotiable)
- **Quarterly**: Review for regulatory changes (FCC rulings, state laws)
- **Annually**: Full compliance audit including consent records, message logs, delivery reports

### White-Label Compliance Considerations
When onboarding new client companies:
- Each white-label deployment must use the client's company name in messages
- Consent is company-specific (worker consents to receive messages from Company A, not Company B)
- If a worker changes employers, new consent is required for the new company
- Client company logos and names in SMS must match the brand registration context
- Consider whether each major client needs its own campaign registration or if one "Mixed" campaign covers all

---

## QUICK REFERENCE — PRE-SUBMISSION FINAL CHECK

Before clicking Submit, verify ALL of these:

- [ ] Brand is approved (Standard or LVS preferred if you have EIN)
- [ ] Campaign description is 2+ sentences, specific, names the business
- [ ] All 5 sample messages filled, each includes "Safety as a Contact" brand name
- [ ] At least one sample includes "Reply STOP to opt out"
- [ ] At least one sample is the opt-in confirmation message
- [ ] At least one sample shows the proactive coaching nudge feature
- [ ] At least one sample shows the AI hazard coaching response
- [ ] Message flow describes WHERE, HOW, and WHAT of consent collection
- [ ] Message flow describes double opt-in (initial text + YES confirmation)
- [ ] Message flow mentions Privacy Policy URL and Terms URL
- [ ] Message flow describes the confirmation message sent after opt-in
- [ ] Privacy Policy URL is live on your domain at /privacy
- [ ] Privacy Policy contains the CTIA non-sharing clause (mobile info not shared)
- [ ] Privacy Policy contains opt-in data exclusion clause
- [ ] Privacy Policy mentions SMS data collection explicitly
- [ ] Terms URL is live on your domain at /terms
- [ ] Terms contains program name, frequency, rates, STOP, HELP, carrier disclaimer
- [ ] Terms states "consent is not a condition of employment"
- [ ] SMS enrollment section visible on website with unchecked checkbox
- [ ] Content checkboxes accurately reflect what's in your messages (all unchecked for our use case)
- [ ] No bit.ly or tinyurl in any sample message
- [ ] No SHAFT content anywhere
- [ ] Support email matches business domain (not gmail/yahoo)
- [ ] Legal business name matches IRS records exactly
- [ ] EIN matches IRS records exactly
- [ ] Physical address matches IRS records (not a PO box)
- [ ] Opt-in keywords include YES, START
- [ ] Opt-out keywords include STOP
- [ ] HELP keyword response includes brand name + contact info
- [ ] Website is SSL-secured, mobile-friendly, loads correctly
- [ ] All website pages accessible without login

---

*Sources: Twilio docs, CTIA Messaging Principles (May 2023), TCR guidelines, TCPA (47 U.S.C. § 227), FCC Declaratory Ruling CG Docket No. 02-278, 60+ community posts, blog articles, and compliance guides. Compiled March 2026. Includes real-world submission experience.*
