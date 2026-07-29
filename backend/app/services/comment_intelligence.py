"""Deterministic comment classification & prioritization.

No LLM, no ML — a fixed set of heuristics, same spirit as
`services/intelligence/title_patterns.py`. Classification is deliberately worded as
a hedge ("Prawdopodobne pytanie" — "Likely question"), never a certainty, since a
question mark or interrogative word is a strong but imperfect signal.

Release 0.7.1 replaced the original "answered = any reply exists from the
channel" logic (which incorrectly marked a thread "answered" even after the
viewer replied again afterward) with a proper conversation-state engine — see
`determine_conversation_state` and ADR-019 in docs/DECISIONS.md. This is now the
ONE place conversation state is computed; every consumer (Inbox, Home, Video
Detail, priority, filters) must call it rather than re-deriving state locally.
"""

import re
from datetime import datetime, timezone
from enum import Enum

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


# ---------------------------------------------------------------------------
# Conversation state engine — Release 0.7.1 / Part 1
# ---------------------------------------------------------------------------


class ConversationState(str, Enum):
    RESOLVED = "resolved"  # last message in the thread belongs to the connected channel
    WAITING = "waiting"  # last message belongs to another user; channel HAS replied before
    NEW = "new"  # the connected channel has never replied in this thread
    CLOSED = "closed"  # unavailable / moderated — nothing actionable here


CONVERSATION_STATE_META: dict[str, dict[str, str]] = {
    ConversationState.RESOLVED.value: {"emoji": "🟢", "text": "Rozwiązane"},
    ConversationState.WAITING.value: {"emoji": "🟡", "text": "Czeka na odpowiedź"},
    ConversationState.NEW.value: {"emoji": "🔵", "text": "Nowy"},
    ConversationState.CLOSED.value: {"emoji": "⚪", "text": "Zamknięty"},
}


def determine_conversation_state(*, has_own_reply: bool, last_message_is_own: bool, is_moderated: bool) -> ConversationState:
    """The single conversation-state rule for the whole app (ADR-019):
    - CLOSED first — a moderated/unavailable thread has nothing actionable.
    - NEW — the channel has never replied here at all, regardless of who's "last".
    - RESOLVED — the channel's reply is the most recent message in the thread.
    - WAITING — the channel has replied before, but the viewer spoke again since.
    Always evaluated against the FULL thread (top-level comment + every reply),
    never the top-level comment alone."""
    if is_moderated:
        return ConversationState.CLOSED
    if not has_own_reply:
        return ConversationState.NEW
    if last_message_is_own:
        return ConversationState.RESOLVED
    return ConversationState.WAITING


RECENCY_WINDOW_DAYS = 30
RECENCY_MAX_POINTS = 30
QUESTION_POINTS = 50
LIKE_POINTS_CAP = 10
REPLY_POINTS_CAP = 10


def comment_priority_score(
    *,
    state: ConversationState,
    is_question: bool,
    last_message_at: datetime,
    like_count: int,
    reply_count: int,
    now: datetime | None = None,
) -> float:
    """Deterministic priority score — higher means more urgent to address.
    Resolved and closed conversations always score 0 — there is nothing left to
    prioritize once the channel has the last word, or the thread is unavailable
    (Part 2: "never prioritize already resolved conversations"). Composition, in
    priority order (explained via UI tooltip):
      - +50 if likely a question
      - up to +30 for recency of the LAST message in the thread (whoever sent it —
        a conversation that just went quiet is more urgent than a stale one),
        linear decay to 0 over RECENCY_WINDOW_DAYS
      - up to +10 for like count (capped, so one viral comment can't dominate)
      - up to +10 for reply count (capped) — an active sub-thread deserves attention
    """
    if state in (ConversationState.RESOLVED, ConversationState.CLOSED):
        return 0.0
    now = now or datetime.now(timezone.utc)
    score = 0.0
    if is_question:
        score += QUESTION_POINTS
    age_days = max(0, (now - _ensure_aware(last_message_at)).days)
    score += max(0, RECENCY_WINDOW_DAYS - age_days) / RECENCY_WINDOW_DAYS * RECENCY_MAX_POINTS
    score += min(LIKE_POINTS_CAP, like_count)
    score += min(REPLY_POINTS_CAP, reply_count)
    return round(score, 2)
