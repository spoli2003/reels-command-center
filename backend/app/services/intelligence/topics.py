"""Deterministic Polish title tokenization + keyword-stem topic clustering.

No embeddings, no similarity scoring, no fixed taxonomy — topics emerge from
whatever significant words actually repeat across a channel's own titles, so the
same algorithm works for any creator/niche. Ported from the frontend's
lib/youtube-metrics.ts (Sprint 1.1) so both layers apply an identical, documented
heuristic rather than two subtly different ones.
"""

import re
from dataclasses import dataclass, field

from .content_metrics import median_or_none
from .types import DerivedItem, Trend

STOPWORDS = {
    "i", "w", "we", "na", "do", "z", "ze", "że", "żeby", "jak", "co", "się", "nie", "to", "ten", "ta", "te", "tym",
    "tego", "tej", "tych", "o", "po", "za", "przez", "dla", "czy", "jest", "są", "był", "była", "było", "będzie",
    "będą", "aby", "ale", "lub", "oraz", "albo", "może", "można", "gdy", "gdzie", "kiedy", "dlaczego", "jaki",
    "jaka", "jakie", "jakich", "który", "która", "które", "którzy", "których", "bez", "pod", "nad", "przed",
    "między", "od", "u", "tak", "tylko", "już", "jeszcze", "też", "bardzo", "właśnie", "czym", "kim", "jego",
    "jej", "ich", "mój", "moja", "moje", "twój", "twoja", "twoje", "swój", "swoja", "swoje", "nasz", "wasz",
    "sobie", "siebie", "mnie", "cię", "ci", "mi", "go", "ją", "je", "nam", "wam", "im", "tu", "tam", "tutaj",
    "teraz", "zawsze", "nigdy", "wszystko", "wszyscy", "każdy", "każda", "każde", "inny", "inna", "inne", "jeden",
    "jedna", "jedno", "dwa", "trzy", "coś", "ktoś", "nic", "kto", "której", "którym", "którego", "niż", "więc",
    "czyli", "ponieważ", "zatem", "a", "czyż", "aż",
    # Generic function/verb words that otherwise cluster unrelated videos into a meaningless "topic"
    # (found by inspecting real clustering output — e.g. "przy" is a preposition, not a subject).
    "przy", "mieć", "mogą", "może", "wiele", "tysiące", "złotych", "liczy", "warto", "trzeba", "będziesz", "masz",
}

MULTI_CHAR_SUFFIXES = ["ami", "ach", "owi", "ów", "emu", "ego", "ymi", "imi", "iem", "om"]
SINGLE_CHAR_SUFFIXES = ["a", "e", "i", "y", "u", "o", "ą", "ę"]
MIN_STEM_LENGTH = 4
MIN_WORD_LENGTH = 4
MIN_TOPIC_VIDEOS = 2

_WORD_SPLIT_RE = re.compile(r"[^\w]+", re.UNICODE)


def stem_word(word: str) -> str:
    for suffix in MULTI_CHAR_SUFFIXES:
        if len(word) - len(suffix) >= MIN_STEM_LENGTH and word.endswith(suffix):
            return word[: -len(suffix)]
    for suffix in SINGLE_CHAR_SUFFIXES:
        if len(word) - 1 >= MIN_STEM_LENGTH and word.endswith(suffix):
            return word[:-1]
    return word


def tokenize_title(title: str) -> list[str]:
    lowered = title.lower()
    words = [w for w in _WORD_SPLIT_RE.split(lowered) if w]
    return [w for w in words if len(w) >= MIN_WORD_LENGTH and w not in STOPWORDS and not w.isdigit()]


@dataclass
class TopicSummary:
    keyword: str
    video_count: int
    median_views: float
    median_views_per_day: float
    median_engagement: float
    best_video_id: str
    worst_video_id: str
    trend: str
    supporting_video_ids: list[str] = field(default_factory=list)


def cluster_topics(items: list[DerivedItem]) -> list[TopicSummary]:
    groups: dict[str, dict] = {}
    for item in items:
        for word in set(tokenize_title(item.title)):
            stem = stem_word(word)
            group = groups.setdefault(stem, {"forms": {}, "items": {}})
            group["forms"][word] = group["forms"].get(word, 0) + 1
            group["items"][item.id] = item

    summaries: list[TopicSummary] = []
    for group in groups.values():
        members = list(group["items"].values())
        if len(members) < MIN_TOPIC_VIDEOS:
            continue
        display_word = max(group["forms"].items(), key=lambda pair: pair[1])[0]
        best = max(members, key=lambda m: m.views_per_day)
        worst = min(members, key=lambda m: m.views_per_day)
        trend_votes = [m.trend.value for m in members if m.trend != Trend.INSUFFICIENT_DATA]
        trend = max(set(trend_votes), key=trend_votes.count) if trend_votes else Trend.INSUFFICIENT_DATA.value
        summaries.append(
            TopicSummary(
                keyword=display_word,
                video_count=len(members),
                median_views=median_or_none([m.views for m in members]) or 0,
                median_views_per_day=median_or_none([m.views_per_day for m in members]) or 0,
                median_engagement=median_or_none([m.engagement_rate for m in members]) or 0,
                best_video_id=best.id,
                worst_video_id=worst.id,
                trend=trend,
                supporting_video_ids=[m.id for m in members],
            )
        )
    summaries.sort(key=lambda summary: summary.video_count, reverse=True)
    return summaries
