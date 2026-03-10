# Behavioral Science Framework Reference
## Safety as a Contact: Why the Product Works

This document explains the behavioral science foundations of Safety as a Contact, an SMS-based behavioral safety coaching platform for construction. It maps seven frameworks to specific code decisions so Claude Code can implement features correctly.

---

## 1. Operant Conditioning (Skinner)
**The Science**: Behavior shaped by consequences. Positive reinforcement increases recurrence.

**Product Implementation**: Every observation gets immediate positive reinforcement. The AI ALWAYS acknowledges first, coaches second. During habit-formation, use continuous reinforcement (every report gets response). As engagement deepens, vary response depth (variable-ratio schedule).

**Code Implication**: The coaching engine must NEVER skip acknowledgment. Response mode selection factors in engagement history—new workers get consistent full responses, experienced workers get varied depth.

**Files**: `coaching/engine.py` (acknowledge before coach), `coaching/prompts.py` (response templates)

---

## 2. Motivational Interviewing (Miller & Rollnick)
**The Science**: Collaborative counseling. Principles: express empathy, develop discrepancy, roll with resistance, support self-efficacy.

**Product Implementation**: AI validates before guiding. When workers express frustration or skepticism, use reflective techniques, not directives. Never assign blame. Build worker identity as competent safety observer.

**Code Implication**: System prompt must encode MI principles. AFFIRM mode is pure self-efficacy building. When sentiment analysis detects negativity/resistance, route to reflective patterns. Use collaborative language ("What do you think...?") not imperatives ("You must...").

**Files**: `coaching/prompts.py` (system prompt), `coaching/sentiment.py` (resistance detection)

---

## 3. Self-Determination Theory (Deci & Ryan)
**The Science**: Motivation depends on autonomy, competence, and relatedness.

**Product Implementation**:
- Autonomy: Workers choose when/what to report. Opt-in system.
- Competence: Each response builds trade-specific knowledge, calibrated to experience level.
- Relatedness: Observations connect to group safety via toolbox talks—workers see their input matters.

**Code Implication**: Never implement mandatory/surveillance features. Experience calibration in coaching engine. Toolbox talks must reference originating observations (anonymized).

**Files**: `coaching/trades.py` (calibration), `feedback/toolbox.py` (relatedness loop)

---

## 4. Social Learning Theory (Bandura)
**The Science**: People learn observing others. Self-efficacy and observational learning critical. Four processes: attention, retention, reproduction, motivation.

**Product Implementation**: When observations become toolbox talks, crew witnesses positive outcome of reporting (modeling effect). AI serves as "More Knowledgeable Other" with scaffolded learning.

**Code Implication**: Toolbox talks anonymously credit worker observations. AI calibrates complexity by experience level—apprentice gets foundational guidance, journeyman gets deeper analysis. Experience_level field drives calibration.

**Files**: `feedback/toolbox.py` (credit mechanism), `coaching/trades.py` (scaffolding)

---

## 5. Psychological Safety (Edmondson)
**The Science**: Teams feeling safe to speak up report more errors AND perform better. Correlation with learning: r=0.80.

**Product Implementation**: Anonymous reporting removes retaliation fear. SMS bypasses chain of command. AI never blames—only coaches and validates. Same response quality regardless of role.

**Code Implication**: Anonymous reporting mandatory—not optional. worker_id field NULLABLE. Response quality invariant by role. No traceability unless worker self-identifies.

**Files**: `models/observations.py` (nullable worker_id), `coaching/engine.py` (role-invariant quality)

---

## 6. Fogg Behavior Model (B=MAP)
**The Science**: Behavior = Motivation + Ability + Prompt. All three must converge.

**Product Implementation**:
- Motivation: Coaching reinforces intrinsic motivation, validates competence, creates proof via toolbox talks
- Ability: SMS is lowest friction. No app, login, or form. All Fogg "simplicity factors" minimized.
- Prompt: Phone always present. Shift-start nudges add temporal prompts.

**Code Implication**: NEVER add reporting friction. If a feature makes texting harder, reject it. Shift-start nudges implemented as scheduled jobs, not manual actions.

**Files**: `sms/handler.py` (frictionless flow), `feedback/nudges.py` (prompt system)

---

## 7. Nudge Theory (Thaler & Sunstein)
**The Science**: Subtle choice presentation influences decisions without restricting freedom. Good choice architecture makes desired behavior the default.

**Product Implementation**: Saved phone number is persistent cue. Texting as easy behavior makes safety the default. Toolbox talks create social nudge where reporting becomes normal.

**Code Implication**: Onboarding: save number → text anything → you're in. No complex enrollment. Consent must feel natural (even if rigorous legally).

**Files**: `sms/consent.py` (natural flow), `onboarding/flow.py` (simplicity)

---

## 8. Habit Loop (Duhigg)
**The Science**: Cue → Routine → Reward. Dopamine release strengthens neural pathway. Behavior transfers from prefrontal cortex (deliberate) to basal ganglia (automatic).

**Product Implementation**:
- Cue: Worker observes hazard
- Routine: Worker texts observation
- Reward: Immediate coaching response
- Evolution: Cue broadens, routine automates, reward compounds via toolbox recognition

**Code Implication**: Response time critical—seconds, not minutes. Reward must feel immediate. Track engagement frequency (engagement_metrics table) to measure habit formation.

**Files**: `coaching/engine.py` (response timing), `models/engagement_metrics.py` (tracking)

---

## Critical Implementation Rules
These rules derive directly from behavioral science. **Violating them breaks the entire product psychology.**

1. **NEVER skip acknowledgment before coaching** — violates operant conditioning
2. **NEVER use blame or imperative language** — violates MI and psychological safety
3. **NEVER force identification** — violates psychological safety
4. **NEVER add friction to reporting** — violates Fogg model (B=MAP)
5. **ALWAYS calibrate to trade and experience** — satisfies SDT competence need
6. **ALWAYS close feedback loops visibly** — satisfies SDT relatedness need
7. **ALWAYS respond in seconds** — habit loop reward timing critical
8. **ALWAYS make anonymous reporting available** — Edmondson's core finding: anonymity enables safety

---

## Framework Integration Reference
| Framework | Feature | Code Component |
|-----------|---------|-----------------|
| Operant Conditioning | Immediate responses | coaching/engine.py |
| Motivational Interviewing | Non-directive tone | coaching/prompts.py |
| Self-Determination | Opt-in + trade calibration | coaching/trades.py |
| Social Learning | Toolbox talks | feedback/toolbox.py |
| Psychological Safety | Anonymous reporting | models/observations.py |
| Fogg Behavior Model | SMS frictionless flow | sms/handler.py |
| Nudge Theory | Zero-friction onboarding | sms/consent.py |
| Habit Loop | Fast reward delivery | coaching/engine.py |

---

## When Making Implementation Decisions
Ask yourself: **Which behavioral framework does this feature serve?** If you can't name one, or if implementing it requires violating a critical rule, it doesn't belong in this product.
