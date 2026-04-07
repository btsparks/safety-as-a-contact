# Telnyx 10DLC Brand & Campaign Registration

## CRITICAL: Brand verification matches against IRS records exactly.
## Every character must match. "Street" vs "St." will cause permanent failure.

---

## Brand Registration Details

Enter these EXACTLY as shown (from IRS Notice CP575G dated March 12, 2026):

| Field | Value |
|-------|-------|
| **Legal Business Name** | BRYAN TRAVIS SPARKS |
| **DBA / Trade Name** | SAFETY AS A CONTACT |
| **EIN / Tax ID** | 41-4833988 |
| **Street Address** | 2730 E STANFORD LN |
| **City** | HOLLADAY |
| **State** | UT |
| **ZIP** | 84117 |
| **Country** | US |
| **Entity Type** | Sole_Proprietor |
| **Company Website** | https://safetyasacontact.com |
| **Vertical** | Construction |
| **Stock Exchange** | (leave blank -- not publicly traded) |

**Name Control:** SPAR

**Notes:**
- Use ALL CAPS for business name and address exactly as shown on CP-575G
- Do NOT use "Holladay" -- use "HOLLADAY"
- Do NOT use "2730 East Stanford Lane" -- use "2730 E STANFORD LN"
- The IRS assigned this EIN on March 12, 2026
- Entity type is Sole_Proprietor (NOT Private_Profit -- this is not an LLC)
- Legal business name is the sole proprietor's personal name, NOT the DBA
- The DBA "SAFETY AS A CONTACT" may appear as a trade name field if TCR has one

---

## Campaign Registration Details

| Field | Value |
|-------|-------|
| **Use Case** | Low Volume Mixed |
| **Sub Use Case** | Customer Care / Mixed |
| **Content Type** | Non-marketing -- worker-initiated safety coaching |
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

> Safety as a Contact provides SMS-based workplace safety coaching for construction workers. Workers text photos and descriptions of jobsite hazard observations to a dedicated phone number. The system responds with AI-powered coaching that references the worker's company safety policies, site-specific safety plans, OSHA standards, and incident reports that have been uploaded by the company's safety director. Messages include safety document references with source attribution, behavioral reflection questions, and acknowledgments of worker observations. All messaging is worker-initiated -- the system only sends messages in direct response to worker texts. No marketing, promotional, or unsolicited messages are ever sent. The program supports English and Spanish. Maximum message frequency is 5 per day during business hours (8 AM - 9 PM local time). Workers opt in via web form at safetyasacontact.com/consent or SMS double opt-in, and can opt out at any time by texting STOP.

### Sample Messages (submit all 5)

**Sample 1 -- Document reference response (English):**
> Jake, your site safety plan covers fall protection for this type of work in Section 3.2. Who else on your crew has seen this area today?

**Sample 2 -- Document reference response (Spanish):**
> Miguel, el plan de seguridad del sitio cubre proteccion contra caidas para este tipo de trabajo. Quien mas en tu equipo ha visto esta area hoy?

**Sample 3 -- Reflective coaching response:**
> Got your photo -- lot going on there. What caught your eye about this spot?

**Sample 4 -- Opt-in confirmation:**
> Safety as a Contact: You're signed up for safety coaching via text. Send a photo of any jobsite observation and we'll respond with relevant safety info. Msg frequency varies, max 5/day. Reply HELP for help, STOP to cancel. Msg & data rates may apply.

**Sample 5 -- Opt-out confirmation:**
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
  - `TELNYX_API_KEY` -- from Telnyx portal > API Keys
  - `TELNYX_PHONE_NUMBER` -- the purchased number in E.164 format
  - `TELNYX_MESSAGING_PROFILE_ID` -- from Messaging > Profiles
  - `TELNYX_PUBLIC_KEY` -- from Telnyx portal (for webhook verification)
- [ ] Send a test message to yourself
- [ ] Reply to verify inbound webhook works
- [ ] Send a photo to verify MMS handling + photo download
- [ ] Text STOP to verify opt-out
- [ ] Text START to verify re-subscribe
- [ ] Text HELP to verify help response
