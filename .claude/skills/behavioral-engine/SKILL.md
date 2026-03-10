---
name: behavioral-engine
description: Behavioral science implementation guide. Auto-invokes when working on coaching logic, feedback loops, or engagement metrics. Ensures all features align with the 8 behavioral frameworks.
allowed-tools: Read, Grep, Bash, Edit, Write
---

# Behavioral Engine Skill

## 8 Behavioral Frameworks (Quick Reference)

| Framework | Code Implications | Example |
|-----------|------------------|---------|
| **Habit Formation** | Track observation frequency, celebrate milestones (3x, 10x, 30x) | Send: "3 observations this week. You're becoming a spotter." |
| **Social Proof** | Anonymous aggregates ("Your crew spotted 12 hazards this week") | Toolbox talk: "Team hazard count this week: 12" |
| **Autonomy** | Never mandate reporting; always empower choice | Never: "You must observe." Always: "You can spot it." |
| **Mastery** | Calibrate coaching depth to trade & experience level | Foreman gets deeper probe questions than apprentice |
| **Loss Aversion** | Frame hazard as "risk reduction," not fear | Not: "You could die." Say: "This removes that risk layer." |
| **Reciprocity** | Feedback loop: worker observation → action → confirmation → gratitude | "Thanks for spotting that pinch point. We fixed it." |
| **Peer Influence** | Toolbox talks reference originating observations (anonymized) | "Someone spotted a rigging angle issue. Here's the math." |
| **Identity** | Workers self-identify as "hazard spotters" not "reporters" | Affirm: "You're becoming a hazard spotter on this team." |

## Feedback Loop Implementation

**Observation → Toolbox Talk → Confirmation**

1. **Worker observation** → Hazard text received (e.g., "Ladder angle looks off")
2. **Coach response** → Immediate SMS coaching
3. **Toolbox talk** → Hazard added to weekly toolbox talk queue (anonymized)
4. **Foreman action** → Hazard discussed, corrected, root cause noted
5. **Confirmation sent** → Worker receives: "Thanks for that ladder observation last week. We recalibrated the angle on the job. Great catch."

**Anonymization rules**:
- Remove worker name, phone, exact location
- Aggregate trades if multi-craft hazard
- Reference only hazard type: "A ladder angle issue was spotted"
- Never name individuals in toolbox talk

**Database schema**:
```sql
CREATE TABLE observations (
  id, phone_number, hazard_type, trade, coaching_response_id,
  referred_to_toolbox_talk BOOLEAN, feedback_sent_at TIMESTAMP
);
```

## Safety Engagement Score Calculation

**Composite formula** (0–100 scale):

```
SES = (30% × obs_frequency) + (25% × obs_quality) +
      (20% × coaching_response_rate) + (15% × feedback_closure) +
      (10% × participation_breadth)
```

- **obs_frequency**: Observations/week (max 10/week = 100%)
- **obs_quality**: Coach validates hazard as legitimate (% of marked valid)
- **coaching_response_rate**: Worker engages with follow-up probe (% replied)
- **feedback_closure**: Observation referred to toolbox + feedback sent (0–100%)
- **participation_breadth**: Hazard types observed (max 8 trade categories = 100%)

**Use cases**:
- Individual: Show in mobile dashboard (private)
- Team: Show trend in weekly foreman report
- Never use as performance metric or tie to compensation

## Proactive Shift-Start Nudge Logic

**When to send** (morning, before shift):
- 30 minutes before scheduled shift start (from worker profile)
- Only if worker has opted in and not already observed today
- Only if prior day had toolbox talk or observation from worker

**What to send** (trade-contextualized, project-specific):
```
Morning brief for [TRADE]: We discussed [HAZARD TYPE] in yesterday's
toolbox talk. Eyes on that today. Text anytime you spot a risk.
```

**Compliance checks**:
- [ ] Consent record active = true
- [ ] Current time in 8am–9pm window (recipient timezone)
- [ ] Phone number not on do-not-contact list
- [ ] No more than 1 nudge per 24 hours

## Anti-Patterns to Avoid

**Surveillance features** → Can use observations for coaching, NOT for policing
- Never: "Worker spotted 0 hazards this week" (shaming)
- Never: Track individual worker by name for management review

**Blame assignment** → Never name individuals or assign fault
- Never: "[Worker A] didn't follow protocol"
- Never: Observations tied to disciplinary action

**Forced identification** → Always optional
- Never: "You must tell us your name to get coaching"
- Allow anonymous observation + optional worker ID

**Mandatory usage tracking** → Participation is voluntary
- Never: "You must text 5 hazards/week"
- Never: Tie observation count to job retention

**Punitive metrics** → No worker penalty for low engagement
- Never: Dashboard showing "low reporters"
- Never: Public ranking of observation frequency

## Decision Framework

**Before implementing any feature, ask**:
1. Which behavioral framework does this serve? (identity, autonomy, reciprocity, etc.)
2. Does it empower workers or constrain them?
3. Could it be misused for punishment or surveillance?
4. If answer to Q3 is "yes," reconsider the feature.

**Example decision**:
- Feature: "Show team observation leaderboard"
- Q1: Social proof, peer influence
- Q2: Empower (celebrates spotters, creates positive norm)
- Q3: Could be misused (shame low reporters)
- Recommendation: Build WITH safeguards (anonymized, no individual names, celebrate category not person)

**Red flag questions**:
- Does this collect data workers don't expect?
- Could a supervisor use this against a worker?
- Does this require workers to identify themselves to participate?
- Would a worker opt out of this feature if given choice?

If "yes" to any, redesign.
