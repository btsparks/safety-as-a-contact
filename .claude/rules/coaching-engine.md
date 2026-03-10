---
paths:
  - "src/coaching/**/*.py"
  - "tests/test_coaching/**/*.py"
---

# Coaching Engine Rules

Rules for the coaching engine:

## Response Structure and Pattern
- Every coaching response MUST follow the pattern: Acknowledge -> Coach -> Empower
- Response validation: Check length (target 1-2 SMS segments), tone (no blame), completeness (all 3 parts)
- All Claude API calls must use the behavioral coaching system prompt from coaching/prompts.py
- Response mode selection (Alert/Validate/Nudge/Probe/Affirm) must be logged

## Language and Tone Requirements
- Never use blame language (your fault, you should have, you failed to, why didn't you)
- Never use imperative commands (you must, you need to, do this immediately)
- Use collaborative language (what do you think, let's work through, have you considered)
- Include OSHA standard references when relevant to hazard type

## Worker Context and Privacy
- Responses must be calibrated to worker's trade (12 trades) and experience level
- Anonymous observations (worker_id=None) get identical quality responses
- Never reference the worker's identity in responses unless they explicitly identified themselves

## Testing Requirements
- Test every response mode with at least 3 different trade contexts
- Verify that anonymous workers receive equal quality responses as identified ones
- Test response calibration across different experience levels
