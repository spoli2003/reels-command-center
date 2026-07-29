"""Deterministic comment classification & prioritization (Release 0.7.0 / Part 8).

No LLM, no ML — a fixed set of heuristics, same spirit as
`services/intelligence/title_patterns.py`. Classification is deliberately worded as
a hedge ("Prawdopodobne pytanie" — "Likely question"), never a certainty, since a
question mark or interrogative word is a strong but imperfect signal.
"""

import re
from datetime import datetime, timezone

QUESTION_MARK_PATTERN = re.compile(r"[?？]")

# Common Polish interrogative sentence-starters (lowercased, leading substring match).
POLISH_INTERROGATIVE_STARTERS = (
    "czy ",
    "jak ",
    "jaki ",
    "jaka ",
    "jakie ",
    "jacy ",
    "gdzie ",
    "kiedy ",
    "dlaczego ",
    "po co",
    "ile ",
    "kto ",
    "kogo ",
    "komu ",
    "który",
    "która",
    "które",
    "czym ",
    "co to",
    "co z ",
    "za co",
    "na czym",
    "od czego",
)

# Direct requests for clarification, anywhere in the text.
CLARIFICATION_PHRASES = (
    "nie rozumiem",
    "moze pan wyjasnic",
    "może pan wyjaśnić",
    "możesz wyjaśnić",
    "możesz to wyjaśnić",
    "proszę o wyjaśnienie",
    "co pan ma na myśli",
    "co ma pani na myśli",
    "co masz na myśli",
    "mógłby pan",
    "mogłaby pani",
    "czy mógłby",
    "czy mogłaby",
    "jak to możliwe",
    "a co jeśli",
)


def is_likely_question(text: str) -> bool:
    """Cautious heuristic — callers must present this as "Prawdopodobne pytanie",
    never as a certainty. True if the text has a question mark, starts with a
    common Polish interrogative word, or contains a direct clarification request."""
    normalized = text.strip().lower()
    if not normalized:
        return False
    if QUESTION_MARK_PATTERN.search(normalized):
        return True
    if normalized.startswith(POLISH_INTERROGATIVE_STARTERS):
        return True
    if any(phrase in normalized for phrase in CLARIFICATION_PHRASES):
        return True
    return False


def _ensure_aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


RECENCY_WINDOW_DAYS = 30
RECENCY_MAX_POINTS = 30
QUESTION_POINTS = 50
LIKE_POINTS_CAP = 10
REPLY_POINTS_CAP = 10


def comment_priority_score(
    *,
    is_unanswered: bool,
    is_question: bool,
    published_at: datetime,
    like_count: int,
    reply_count: int,
    now: datetime | None = None,
) -> float:
    """Deterministic priority score — higher means more urgent to address.
    Answered comments always score 0 (nothing to prioritize). Composition, in
    priority order (explained via UI tooltip, Part 8):
      - +50 if likely a question
      - up to +30 for recency (linear decay to 0 over RECENCY_WINDOW_DAYS)
      - up to +10 for like count (capped, so one viral comment can't dominate)
      - up to +10 for reply count (capped) — an active sub-thread deserves attention
    """
    if not is_unanswered:
        return 0.0
    now = now or datetime.now(timezone.utc)
    score = 0.0
    if is_question:
        score += QUESTION_POINTS
    age_days = max(0, (now - _ensure_aware(published_at)).days)
    score += max(0, RECENCY_WINDOW_DAYS - age_days) / RECENCY_WINDOW_DAYS * RECENCY_MAX_POINTS
    score += min(LIKE_POINTS_CAP, like_count)
    score += min(REPLY_POINTS_CAP, reply_count)
    return round(score, 2)
