"""Small talk detection and replies.

The SOP mode is deliberately strict: when retrieval finds nothing it refuses,
because inventing an organisational procedure is the worst thing this product
could do. Applied literally, though, that rule also rejects a greeting — "Hi"
retrieves nothing, so the assistant answered a friendly hello with a compliance
refusal.

Small talk is therefore recognised before retrieval and answered directly. The
check is deliberately conservative: it only fires when *every* word is a known
pleasantry, so anything substantive still goes through the grounded pipeline.
That keeps the refusal guarantee intact for real questions.
"""

import re

# Words that may appear in a message that is purely social. Everything after
# punctuation removal must be in this set for the message to count as small talk.
_PLEASANTRY = {
    "hi", "hii", "hiii", "hey", "heyy", "hello", "helo", "yo", "sup",
    "good", "morning", "afternoon", "evening", "day", "night",
    "there", "you", "u", "are", "is", "it", "how", "whats", "what", "howdy",
    "thanks", "thank", "thx", "ty", "cheers", "appreciated", "appreciate",
    "ok", "okay", "k", "cool", "great", "nice", "alright", "sure", "yes",
    "bye", "goodbye", "cya", "later", "please", "pls", "welcome", "no", "np",
    "sopia", "again", "so", "and", "the", "a", "im", "i", "am", "fine", "doing",
}

# Whole-message phrases that ask what the assistant is or can do. These are not
# questions about the organisation, so they must not trigger the SOP refusal.
_CAPABILITY_PATTERNS = (
    re.compile(r"^(what|wat) (can|do) (you|u) do\??$"),
    re.compile(r"^(who|what) (are|r) (you|u)\??$"),
    re.compile(r"^what (is|s) (this|sopia)\??$"),
    re.compile(r"^(help|menu|options)\??$"),
    re.compile(r"^(what|which) (can|do) (you|u) help( me)?( with)?\??$"),
)

# Require the greeting to be reasonably short so a long message that happens to
# start with "hi" is never treated as small talk.
_MAX_WORDS = 8

_WORD = re.compile(r"[a-z']+")


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def is_small_talk(text: str) -> bool:
    """True when ``text`` is purely social and carries no real question."""
    message = _normalise(text)
    if not message:
        return False

    for pattern in _CAPABILITY_PATTERNS:
        if pattern.match(message):
            return True

    without_punctuation = re.sub(r"[^a-z0-9\s']", " ", message)
    words = _WORD.findall(without_punctuation)
    if not words or len(words) > _MAX_WORDS:
        return False

    return all(word in _PLEASANTRY for word in words)


def reply_to_small_talk(text: str) -> str:
    """A short, friendly reply. Deterministic, so no model call is needed."""
    message = _normalise(text)
    words = set(_WORD.findall(message))

    if words & {"thanks", "thank", "thx", "ty", "cheers", "appreciate", "appreciated"}:
        return (
            "You're welcome. Ask me anything about your organisation's SOPs whenever "
            "you're ready."
        )

    if words & {"bye", "goodbye", "cya", "later"}:
        return "Goodbye. Come back any time you need to check a procedure."

    for pattern in _CAPABILITY_PATTERNS:
        if pattern.match(message):
            return (
                "I'm SOPIA, your organisation's procedure assistant. I answer questions "
                "using only your approved SOPs and show you the exact source for every "
                "answer. I can also run practice interviews, and once you have an account, "
                "learning sessions, exams and progress tracking.\n\n"
                "What would you like to look up?"
            )

    return (
        "Hello! I'm SOPIA. I answer questions using your organisation's approved SOPs "
        "and cite the exact document and section behind each answer.\n\n"
        "Try asking something like \"What must a new client present during "
        "registration?\""
    )
