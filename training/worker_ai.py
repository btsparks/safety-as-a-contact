"""Worker AI — generates realistic worker messages for simulation.

Uses a separate Claude API call (never shares context with the coaching engine)
to produce messages that match a persona's current stage of development.
The worker AI evolves behavior based on session number:
  - Sessions 1-3: starting_behavior
  - Sessions 4-8: blended transition
  - Sessions 9+: growth_trajectory

Chaos modes add controlled randomness to test edge cases:
  - mood_shift: Worker suddenly gets frustrated or distracted
  - language_switch: EN<>ES mid-conversation
  - photo_flood: Multiple photos, no text
  - gibberish: Typos, autocorrect, fragments
  - resistance: Pushback, sarcasm, dismissiveness
  - disagreement: Worker challenges the coach's observation
  - over_eager: Floods with photos and messages
"""

import logging
import random

from backend.config import settings
from training.personas import Persona

logger = logging.getLogger(__name__)

# Chaos mode definitions
CHAOS_MODES = [
    "mood_shift",
    "language_switch",
    "gibberish",
    "resistance",
    "disagreement",
    "over_eager",
]


def _roll_chaos(persona: Persona) -> str | None:
    """Roll dice for chaos mode. Returns mode name or None."""
    if persona.chaos_probability <= 0:
        return None
    if random.random() < persona.chaos_probability:
        return random.choice(CHAOS_MODES)
    return None


def _build_chaos_instruction(chaos_mode: str, persona: Persona) -> str:
    """Build chaos mode instruction for the worker AI prompt."""
    instructions = {
        "mood_shift": (
            "CHAOS MODE — MOOD SHIFT: You are suddenly frustrated, rushed, or "
            "distracted. Maybe the foreman just yelled at you, or you're running "
            "behind schedule. Show it in your message — short, irritated, maybe "
            "a little rude. Don't explain why."
        ),
        "language_switch": (
            "CHAOS MODE — LANGUAGE SWITCH: Switch languages mid-message. "
            f"If you normally text in {'Spanish' if persona.language == 'es' else 'English'}, "
            f"suddenly switch to {'English' if persona.language == 'es' else 'Spanish'} "
            "for part of this message. This is natural — bilingual workers do this."
        ),
        "gibberish": (
            "CHAOS MODE — GIBBERISH/TYPOS: Your phone autocorrect is acting up "
            "and you're typing fast with gloves on. Send a message with typos, "
            "autocorrect disasters, fragments, or abbreviations that barely make "
            "sense. Examples: 'thia scafold lookd wronf', 'chk ths out', 'wtf is this'"
        ),
        "resistance": (
            "CHAOS MODE — RESISTANCE: Push back hard. Be sarcastic or dismissive. "
            "You don't want to deal with this right now. Examples: 'yeah ok whatever', "
            "'been doing this longer than you', 'it's fine leave it alone', "
            "'not my problem'. Don't be cooperative."
        ),
        "disagreement": (
            "CHAOS MODE — DISAGREEMENT: The coach said something you disagree with. "
            "Challenge them directly. You think you know better based on your "
            "experience. Examples: 'nah that's not how we do it', 'that's fine the "
            "way it is', 'you're wrong about that'. Be firm but not aggressive."
        ),
        "over_eager": (
            "CHAOS MODE — OVER EAGER: You're extremely excited and sending too much. "
            "Multiple observations in one message. Ask 3 questions at once. "
            "Reference things the coach hasn't seen yet. Be overwhelming."
        ),
    }
    return instructions.get(chaos_mode, "")


def _build_worker_system_prompt(
    persona: Persona,
    session_number: int,
    has_photo: bool,
    coach_message: str | None = None,
    chaos_mode: str | None = None,
) -> str:
    """Build the system prompt for the worker AI."""

    # Determine behavior stage
    if session_number <= 3:
        stage = "EARLY"
        behavior = persona.starting_behavior
    elif session_number <= 8:
        stage = "TRANSITION"
        behavior = (
            f"Blending between starting and growth behavior. "
            f"Starting behavior: {persona.starting_behavior}\n"
            f"Growth trajectory: {persona.growth_trajectory}\n"
            f"You are partway through the transition — session {session_number} of ~10. "
            f"Show some growth but still have old habits."
        )
    else:
        stage = "GROWTH"
        behavior = persona.growth_trajectory

    photo_note = ""
    if has_photo:
        photo_note = (
            "A construction site photo is being shared in this conversation. "
            "Reference things you'd realistically see on a jobsite related to "
            f"your trade ({persona.trade}). Don't describe the photo — "
            "react to it like you took it."
        )

    reply_note = ""
    if coach_message:
        reply_note = (
            f'The coach just said: "{coach_message}"\n'
            "Reply to what they said. Stay in character."
        )

    chaos_instruction = ""
    if chaos_mode:
        chaos_instruction = (
            f"\n{_build_chaos_instruction(chaos_mode, persona)}\n"
            "This overrides your normal engagement style for THIS message only."
        )

    return f"""\
You are {persona.name}, a construction worker. You are texting a safety coach.
Stay 100% in character. Never break character. Never say you are AI.

PERSONA:
{persona.personality}

CURRENT STAGE ({stage} — session {session_number}):
{behavior}

LANGUAGE: {persona.language} ({'Spanish' if persona.language == 'es' else 'English'})
Respond in {persona.language}. {'Use natural Spanish, not translated English.' if persona.language == 'es' else ''}

ENGAGEMENT STYLE: {persona.engagement_style}
{'Keep messages very short — 1-5 words typical.' if persona.engagement_style == 'low' else ''}
{'Messages are moderate length — 1-2 sentences.' if persona.engagement_style == 'medium' else ''}
{'Messages can be detailed — 1-3 sentences. You ask questions back.' if persona.engagement_style == 'high' else ''}

{photo_note}
{reply_note}
{chaos_instruction}

RULES:
- Text like a real construction worker on a phone. Short. No punctuation fuss.
- Match the persona's engagement style and current development stage.
- If early stage and low engagement, single words or very short phrases are fine.
- Never use safety jargon the persona wouldn't know at their current stage.
- Never be overly enthusiastic or unnaturally cooperative.
- Your message should be 1-15 words max (unless high engagement style)."""


def generate_worker_message(
    persona: Persona,
    session_number: int,
    turn_number: int,
    has_photo: bool = False,
    coach_message: str | None = None,
    chaos_mode: str | None = None,
) -> tuple[str, str | None]:
    """Generate a realistic worker message using Claude API.

    Returns (message_text, chaos_mode_used). chaos_mode_used is None if no
    chaos was triggered.

    Falls back to example_messages if no API key is available.
    """
    # Roll for chaos if not explicitly set
    if chaos_mode is None:
        chaos_mode = _roll_chaos(persona)

    if not settings.anthropic_api_key:
        msg = _generate_mock_message(persona, session_number, turn_number, coach_message, chaos_mode)
        return msg, chaos_mode

    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    system = _build_worker_system_prompt(persona, session_number, has_photo, coach_message, chaos_mode)

    user_text = "Send your message."
    if turn_number == 1 and has_photo:
        user_text = "You just took a photo on the jobsite and are sending it to the coach. What do you text with it (if anything)?"
    elif turn_number == 1:
        user_text = "Start a new conversation with the safety coach. Text them."
    elif coach_message:
        user_text = "Reply to the coach's message."

    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=80,
        temperature=0.7,
        system=system,
        messages=[{"role": "user", "content": user_text}],
    )

    return resp.content[0].text.strip(), chaos_mode


def _generate_mock_message(
    persona: Persona,
    session_number: int,
    turn_number: int,
    coach_message: str | None = None,
    chaos_mode: str | None = None,
) -> str:
    """Fallback: pick from example_messages based on stage + chaos."""
    examples = persona.example_messages
    if not examples:
        return "ok"

    # Chaos mode mock messages
    if chaos_mode == "gibberish":
        return random.choice(["thia lookd wronf", "chk ths", "idk man", "wtf", "helo"])
    if chaos_mode == "resistance":
        return random.choice(["whatever", "it's fine", "not my problem", "been doing this 20 years"])
    if chaos_mode == "disagreement":
        return random.choice(["nah that's wrong", "no it's fine", "you're wrong about that"])
    if chaos_mode == "language_switch":
        if persona.language == "es":
            return random.choice(["this thing is messed up mira", "look at esto"])
        else:
            return random.choice(["this thing is no bueno", "check this out, esta mal"])
    if chaos_mode == "mood_shift":
        return random.choice(["forget it", "whatever man", "ugh", "not now"])
    if chaos_mode == "over_eager":
        return "check this out and also that thing over there is that ok? what about the crane?"

    # Normal stage-based selection
    if session_number <= 3:
        pool = examples[: len(examples) // 2] or examples[:1]
    elif session_number <= 8:
        pool = examples[len(examples) // 3 : 2 * len(examples) // 3] or examples
    else:
        pool = examples[len(examples) // 2 :] or examples[-2:]

    return random.choice(pool)
