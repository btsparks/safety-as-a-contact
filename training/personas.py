"""Longitudinal test personas for simulation-driven prompt evaluation.

Each persona represents a realistic construction worker archetype with a
defined growth trajectory. The simulator uses these to generate multi-session
conversations that test the coaching engine's ability to develop workers
over time.
"""

from dataclasses import dataclass, field


@dataclass
class Persona:
    """A test worker persona for longitudinal simulation."""

    name: str
    phone: str
    trade: str
    experience_level: str
    language: str
    personality: str
    starting_behavior: str
    growth_trajectory: str
    example_messages: list[str] = field(default_factory=list)
    photo_frequency: float = 0.8  # fraction of sessions that include a photo
    engagement_style: str = "medium"  # low, medium, high
    chaos_probability: float = 0.0  # 0.0–0.3, triggers edge-case chaos modes


PERSONAS: dict[str, Persona] = {
    "miguel": Persona(
        name="Miguel",
        phone="+19998880001",
        trade="laborer",
        experience_level="entry",
        language="es",
        personality=(
            "Miguel is a 22-year-old laborer on his first big commercial job. "
            "He mostly texts in Spanish, keeps messages very short, and almost "
            "always sends photos without much text. He is eager to learn but "
            "self-conscious about his English. He trusts visual communication "
            "over words."
        ),
        starting_behavior=(
            "Sends photos with zero or minimal text — maybe a single word "
            'like "mira" or "esto." Rarely asks questions. Responds to '
            "coaching with brief acknowledgments: 'ok', 'si', 'ya veo'. "
            "Doesn't identify hazards himself; waits for the coach to point "
            "things out."
        ),
        growth_trajectory=(
            "Begins adding context to photos in Spanish: 'andamio sin barandal' "
            "(scaffold without guardrail). Starts asking questions: "
            "'eso esta bien?' (is that okay?). Develops safety vocabulary in "
            "Spanish. Eventually sends photos proactively before being asked, "
            "and adds trade-specific observations."
        ),
        example_messages=[
            "(photo only)",
            "mira",
            "esto",
            "ok",
            "si",
            "ya veo",
            "que hago?",
            "andamio",
            "eso esta bien?",
            "no tiene barandal",
            "puse cinta amarilla",
        ],
        photo_frequency=0.9,
        engagement_style="low",
        chaos_probability=0.15,  # Occasional language switches, photo-only
    ),
    "jake": Persona(
        name="Jake",
        phone="+19998880002",
        trade="ironworker",
        experience_level="intermediate",
        language="en",
        personality=(
            "Jake is a 30-year-old ironworker, 6 years in the trade. "
            "He's sharp, engaged, and genuinely interested in safety. "
            "Sends detailed messages alongside photos. Asks follow-up "
            "questions. He's the guy other workers ask about rigging "
            "and picks. Comfortable challenging the coach when he disagrees."
        ),
        starting_behavior=(
            "Sends photos with solid context: 'Setting up for a pick on the "
            "north side, rigging looks tight but want a second set of eyes.' "
            "Identifies obvious hazards but misses the bigger picture — "
            "focuses on his immediate task and doesn't scan the broader scene. "
            "Engages in 3-4 turn conversations."
        ),
        growth_trajectory=(
            "Starts asking root cause questions: 'Why does this keep happening "
            "on every pour?' Expands field of view beyond rigging to overhead, "
            "adjacent trades, temporal changes. Begins mentoring language: "
            "'I showed the new guy how to check tag lines.' Eventually identifies "
            "systemic issues, not just point hazards."
        ),
        example_messages=[
            "Setting up for a pick on the north side. Rigging looks tight but want a second set of eyes.",
            "What about the tag lines? We only have two for a three-point pick.",
            "Good point. What else should I be looking at here?",
            "Yeah the crane's been swinging loads over pedestrian traffic all morning.",
            "I'll flag it. Why does this keep happening though?",
            "Showed the apprentice how to inspect shackles today. Kid's getting better.",
        ],
        photo_frequency=0.7,
        engagement_style="high",
        chaos_probability=0.1,  # Occasionally challenges or disagrees
    ),
    "ray": Persona(
        name="Ray",
        phone="+19998880003",
        trade="operating_engineer",
        experience_level="entry",
        language="en",
        personality=(
            "Ray is a 45-year-old operating engineer, new to the trade after "
            "20 years driving trucks. He's skeptical of 'safety programs' — "
            "seen too many that were just paperwork. Gives short, sometimes "
            "sarcastic replies. But he knows equipment better than anyone "
            "and slowly opens up when he realizes the coaching is real, "
            "not corporate BS."
        ),
        starting_behavior=(
            "Minimal engagement. Sends photos only when asked. Replies with "
            "'ok', 'yeah', 'fine'. Occasionally pushes back: 'been doing this "
            "20 years, I know.' Doesn't volunteer observations. Treats the "
            "coaching as an annoyance at first."
        ),
        growth_trajectory=(
            "Gradually starts sending equipment photos without being asked. "
            "Begins sharing equipment-specific knowledge: 'Hydraulic line on "
            "the 330 is seeping. Not a leak yet but it will be.' Shifts from "
            "resistant to sharing expertise. Eventually becomes the equipment "
            "safety resource — 'Tell the new operator to check his ground "
            "conditions before he sets up.'"
        ),
        example_messages=[
            "ok",
            "yeah",
            "fine",
            "been doing this 20 years, I know",
            "it's fine",
            "what do you want me to look at",
            "hydraulic line is seeping a little",
            "not a big deal",
            "alright I'll check it",
            "told the kid to check ground before he sets up",
        ],
        photo_frequency=0.4,
        engagement_style="low",
        chaos_probability=0.2,  # More chaos — resistant, sarcastic, frustrated
    ),
    # --- Edge-case personas for stress testing ---
    "carlos": Persona(
        name="Carlos",
        phone="+19998880004",
        trade="concrete",
        experience_level="intermediate",
        language="es",
        personality=(
            "Carlos is a 35-year-old concrete finisher, bilingual but prefers "
            "Spanish. Switches between English and Spanish mid-conversation "
            "depending on his mood. Sends lots of photos with minimal text. "
            "Gets frustrated when he feels rushed or when safety slows production."
        ),
        starting_behavior=(
            "Sends photos with one-word Spanish labels. Gets frustrated easily. "
            "Sometimes switches to angry English when upset. Responds with 'whatever' "
            "or 'como sea' when he disagrees."
        ),
        growth_trajectory=(
            "Starts adding bilingual context. Frustration becomes constructive — "
            "'esto no funciona asi, hay que hacerlo de otra manera.' Eventually "
            "becomes the bridge between Spanish-speaking crew and English-speaking "
            "supervision."
        ),
        example_messages=[
            "mira esto",
            "whatever",
            "como sea",
            "this is stupid",
            "ya lo se",
            "the forms are wrong again",
            "otra vez lo mismo",
            "look at this mess",
        ],
        photo_frequency=0.8,
        engagement_style="medium",
        chaos_probability=0.3,  # High chaos — language switches, frustration, resistance
    ),
    "diana": Persona(
        name="Diana",
        phone="+19998880005",
        trade="electrician",
        experience_level="entry",
        language="en",
        personality=(
            "Diana is a 24-year-old first-year electrical apprentice. Eager, "
            "asks too many questions, sends multiple photos in rapid succession. "
            "Sometimes floods the coach with messages. Wants validation on "
            "everything because she's the only woman on her crew and feels "
            "extra pressure to prove herself."
        ),
        starting_behavior=(
            "Sends 3-4 photos at once with rapid-fire texts. Asks 'is this right?' "
            "after every task. Over-explains everything. Texts full paragraphs."
        ),
        growth_trajectory=(
            "Learns to focus observations. Stops seeking constant validation. "
            "Develops confident, specific language. Eventually mentors newer "
            "apprentices with the same patience she received."
        ),
        example_messages=[
            "is this right?",
            "ok what about this one",
            "am I doing this wrong",
            "the journeyman said it was fine but I'm not sure",
            "here's another angle",
            "what do you think",
            "I ran it through conduit like he showed me but something looks off",
        ],
        photo_frequency=0.95,
        engagement_style="high",
        chaos_probability=0.15,  # Photo floods, over-eagerness
    ),
}


def get_persona(name: str) -> Persona | None:
    """Get a persona by name (case-insensitive)."""
    return PERSONAS.get(name.lower())


def list_personas() -> list[dict]:
    """Return all personas as serializable dicts for the API."""
    result = []
    for key, p in PERSONAS.items():
        result.append({
            "key": key,
            "name": p.name,
            "phone": p.phone,
            "trade": p.trade,
            "experience_level": p.experience_level,
            "language": p.language,
            "personality": p.personality,
            "starting_behavior": p.starting_behavior,
            "growth_trajectory": p.growth_trajectory,
            "example_messages": p.example_messages,
            "photo_frequency": p.photo_frequency,
            "engagement_style": p.engagement_style,
        })
    return result
