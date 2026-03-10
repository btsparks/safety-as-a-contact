---
paths:
  - "src/sms/**/*.py"
  - "src/api/**/*.py"
  - "tests/test_sms/**/*.py"
---

# SMS Compliance Rules

Rules for any code that touches SMS:

## Consent and Opt-out Requirements
- ALWAYS verify consent before sending any outbound message
- ALWAYS check sending window (8am-9pm recipient's local time)
- ALWAYS include opt-out language in outbound messages
- ALWAYS validate Twilio webhook signatures on inbound requests
- ALWAYS log every message (inbound and outbound) to message_log table
- NEVER send to a phone number with is_active=False in consent_records
- NEVER delete consent records — soft delete only (set revoked_at timestamp)
- NEVER hardcode phone numbers

## Processing Requirements
- Process opt-out keywords (STOP, CANCEL, END, QUIT, UNSUBSCRIBE) immediately
- Use Twilio Messaging Service SID, not raw phone number, for outbound
- All phone numbers stored in E.164 format (+1XXXXXXXXXX)
- Rate limit: No more than 5 outbound messages per phone number per day (excluding opt-out confirmations)

## Logging and Auditing
- Every message (inbound and outbound) must be logged to message_log table
- Include timestamp, phone_number, message content, direction, and status in logs
- Maintain audit trail of all consent state changes
