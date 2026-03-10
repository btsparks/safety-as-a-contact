---
paths:
  - "tests/**/*.py"
  - "tests/**/*.test.*"
---

# Testing Rules

Rules for tests:

## Coaching Engine Tests
- Every coaching response mode must have tests for at least 3 different trades
- Test anonymous observations (worker_id=None) receive identical quality responses as identified ones
- Test response calibration across different experience levels
- Verify the Acknowledge->Coach->Empower pattern in responses
- Validate response length (target 1-2 SMS segments)
- Verify no blame language in responses

## Consent Management Tests
- Opt-in scenario: new consent record created with is_active=True
- Opt-out scenario: process STOP/CANCEL/etc. keywords immediately
- Re-opt-in scenario: insert new record after revoked consent
- Expired consent scenario: handle time-based consent expiration
- Missing consent scenario: reject message send when no active consent

## SMS Compliance Tests
- Sending window enforcement: reject sends outside 8am-9pm local time
- Opt-out keyword processing: immediate handling of STOP, CANCEL, END, QUIT, UNSUBSCRIBE
- Consent verification: validate is_active=True before sending
- Rate limiting: enforce 5 message maximum per phone per day
- Twilio webhook signature validation
- Message logging: verify all messages logged to message_log table

## API Tests
- Every endpoint must have at least 3 tests:
  - Success case: valid request returns expected response
  - Auth failure: missing/invalid auth returns 401
  - Validation error: invalid input returns 400
- Test all error codes and error messages
- Test pagination, filtering, and sorting where applicable

## Mock Requirements
- Mock Twilio API calls in unit tests — never hit real APIs in tests
- Mock Claude API calls in unit tests
- Integration tests can use test Twilio credentials
- Test database operations with a test database, not production

## Edge Cases
- Empty messages
- Very long messages (multi-segment SMS)
- Non-English text and special characters
- Phone number format variations
- Database connection failures
- API timeout scenarios
- Rate limit boundary conditions (4, 5, 6 messages)
