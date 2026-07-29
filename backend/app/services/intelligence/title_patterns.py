"""Deterministic, rule-based title pattern detection. Curated word lists, no ML/sentiment model."""

import re

QUESTION_WORDS = ("czy", "jak", "co", "dlaczego", "kiedy", "ile", "gdzie", "kto", "jaki", "jaka", "jakie")
EMOTIONAL_WORDS = ("szok", "uwaga", "błąd", "błędy", "niebezpieczne", "sekret", "prawda", "ostrzeżenie", "alarm", "dramat")
LEGAL_WORDS = ("ustawa", "prawo", "sąd", "wyrok", "przepis", "kodeks", "adwokat", "sędzia", "pozew")
DEADLINE_WORDS = ("termin", "ostatni dzień", "deadline", "do końca", "wygasa", "ostatnia szansa")

_MONTHS = (
    "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia", "września", "października",
    "listopada", "grudnia",
)
_DATE_PATTERN = re.compile(r"\b\d{1,2}\s+(" + "|".join(_MONTHS) + r")\b", re.IGNORECASE)
_DIGIT_PATTERN = re.compile(r"\d")


def has_question(title: str) -> bool:
    if "?" in title:
        return True
    lowered = title.lower().strip()
    first_word = lowered.split(" ", 1)[0] if lowered else ""
    return first_word in QUESTION_WORDS


def has_number(title: str) -> bool:
    return bool(_DIGIT_PATTERN.search(title))


def has_deadline_wording(title: str) -> bool:
    lowered = title.lower()
    return any(word in lowered for word in DEADLINE_WORDS) or bool(_DATE_PATTERN.search(lowered))


def has_emotional_wording(title: str) -> bool:
    lowered = title.lower()
    return any(word in lowered for word in EMOTIONAL_WORDS)


def has_legal_wording(title: str) -> bool:
    lowered = title.lower()
    return any(word in lowered for word in LEGAL_WORDS)


TITLE_PATTERN_DETECTORS = {
    "question": has_question,
    "number": has_number,
    "deadline": has_deadline_wording,
    "emotional": has_emotional_wording,
    "legal": has_legal_wording,
}

TITLE_PATTERN_LABELS = {
    "question": "Pytanie w tytule",
    "number": "Liczba w tytule",
    "deadline": "Termin / pilność",
    "emotional": "Emocjonalne słownictwo",
    "legal": "Słownictwo prawnicze",
}
