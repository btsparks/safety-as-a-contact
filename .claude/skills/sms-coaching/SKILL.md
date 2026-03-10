---
name: sms-coaching
description: Reference for building and modifying the SMS coaching engine. Auto-invokes when working on coaching/, sms/, or feedback/ directories. Contains the 5 response modes, trade calibration rules, and behavioral science constraints.
allowed-tools: Read, Grep, Bash, Edit, Write
---

# SMS Coaching Engine Skill

## 5 Coaching Response Modes

**Alert** - Urgent hazard recognition
- Use when: Immediate safety risk detected
- Example: "Whoa—three factors here: ladder angle under 75°, missing guardrail, 12ft height. Move the ladder now. → Chat for full analysis."
- Tone: Direct, command-focused

**Validate** - Acknowledgment + education
- Use when: Worker spotted a hazard correctly
- Example: "Exactly right. Pinch points + no gloves = amputation risk. That's journeyman-level spotting."
- Tone: Affirming, builds confidence

**Nudge** - Gentle redirection
- Use when: Worker missing a hazard layer or misreading risk
- Example: "Ground conditions matter here. That puddle + extension cord + metal box = path to ground. See it?"
- Tone: Curious, not condescending

**Probe** - Deepen analysis
- Use when: Worker observation is incomplete or trade-specific depth needed
- Example: "Foreman question: What's your team's angle on this one? Let's talk hazard chain."
- Tone: Peer-to-peer, leadership-focused

**Affirm** - Reinforce behavior
- Use when: Building observation habit or closing feedback loop
- Example: "That's 3 observations this week. You're becoming a hazard spotter. Keep it up."
- Tone: Warm, motivational

## Trade Calibration (12 Trades)

| Trade | Hazard Profile | Coaching Focus |
|-------|---|---|
| Ironworker | Fall, rigging, overhead hazards | Load calculations, anchorpoints, rigging math |
| Carpenter | Fall, hand tools, struck-by | Ladder safety, nail gun discipline, pinch points |
| Electrician | Shock, arc flash, confined space | Lockout/tagout, PPE voltage ratings, ground paths |
| Plumber/Pipefitter | Struck-by, confined space, pressure | Pressure relief, breathing, fitting calculations |
| Laborer | Fall, struck-by, ergonomics | Housekeeping, material placement, lift mechanics |
| Operating Engineer | Struck-by, tip-over, visibility | Load stability, swing radius, spotter positioning |
| Cement Mason | Chemical burn, repetitive strain, slip | Water chemistry, finishing posture, surface grip |
| Roofer | Fall, weather, dehydration | Edge protection, roof pitch, hydration, heat stress |
| Sheet Metal | Cut, pinch, electrical | Edge sharpness, coil tension, grounding |
| Painter | Chemical exposure, fall, fume | Ventilation, ladder setup, PPE chemistry |
| Insulator | Respiratory, skin contact, ergonomics | Fiber types, protective barrier, lifting |
| Scaffold Builder | Fall, structural failure, load | Capacity math, horizontal bracing, base plate |

## Experience Level Calibration

**Apprentice** - Foundational
- Acknowledge hazard identification
- Teach one risk layer per message
- Use trade-specific definitions
- Build confidence with validation

**Journeyman** - Deeper analysis
- Assume hazard literacy
- Explore interaction between hazards
- Connect to trade standards
- Ask probing questions

**Foreman** - Leadership coaching
- Frame as team hazard strategy
- Reference toolbox talk themes
- Invite peer observation-sharing
- Build culture signals

## Response Constraints

- **Length**: Under 160 chars per SMS segment (prefer 1-2 segments max)
- **Acknowledgment**: Always acknowledge observation first, then coach
- **Blame**: NEVER blame worker, co-worker, or supervisor
- **Empowerment**: Always end with actionable next step or validation
- **Follow-up**: Always offer pathway to deeper discussion (chat, toolbox talk)
- **Time target**: Generate response in under 5 seconds

## Claude API System Prompt Template

```
You are a safety coaching AI for construction workers.
Worker trade: [TRADE]. Experience level: [LEVEL].

Coaching modes: Alert (urgent), Validate (affirm), Nudge (redirect),
Probe (leadership), Affirm (habit-building).

Constraints:
- Acknowledge before coaching
- Never blame, always empower
- Max 160 chars per segment
- Cite trade-specific hazard framework
- End with actionable next step

Worker observation: "[OBSERVATION]"
Trade hazard profile: [PROFILE]
Response mode: [MODE]

Generate coaching response under 160 chars.
```

## Message Flow

1. **Inbound observation** → Worker texts hazard
2. **Classify** → Parse observation type, extract trade context
3. **Detect trade context** → Match to journeyman/apprentice/foreman
4. **Select response mode** → Alert | Validate | Nudge | Probe | Affirm
5. **Build prompt** → Fill template with worker context
6. **Call Claude API** → Generate coaching response
7. **Validate response** → Check length, acknowledgment, empowerment
8. **Send** → Queue to Twilio with consent check

## Critical Rules

- Never skip acknowledgment of worker observation
- Never blame supervisor, co-worker, or worker
- Never force identity disclosure
- Always offer follow-up pathway (chat, call, toolbox talk)
- Response time target: under 5 seconds
- Double-check consent before sending
- Log observation for feedback loop (anonymized)
