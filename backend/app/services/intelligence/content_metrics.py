"""Deterministic per-item metric derivation. Platform-agnostic — operates only on
ContentItem/SnapshotPoint. No randomness, no ML: same input always produces the same output.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from statistics import median as _median
from typing import Optional, Sequence

from .types import ContentItem, Confidence, DerivedItem, SnapshotPoint, Trend

MIN_HISTORY_FOR_VELOCITY = 2
MIN_HISTORY_FOR_ACCELERATION = 3
ACCELERATING_RATIO = 1.15
SLOWING_RATIO = 0.5
MIN_HOUR_FRACTION_DAYS = 1 / 24  # floor the divisor so same-day resyncs never produce absurd spikes


def engagement_rate(likes: int, comments: int, views: int) -> float:
    if not views:
        return 0.0
    return round((likes + comments) / views * 100, 2)


def ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _interval_velocity(later: SnapshotPoint, earlier: SnapshotPoint) -> float:
    gap_seconds = (ensure_aware(later.captured_at) - ensure_aware(earlier.captured_at)).total_seconds()
    gap_days = max(gap_seconds / 86400, MIN_HOUR_FRACTION_DAYS)
    return (later.views - earlier.views) / gap_days


def derive(item: ContentItem, now: Optional[datetime] = None) -> DerivedItem:
    """Compute age/views-per-day/engagement/velocity/acceleration/trend for one item."""
    now = now or datetime.now(timezone.utc)
    published_at = ensure_aware(item.published_at)
    age_days = max(0, (now - published_at).days)
    divisor = max(1, age_days)
    views_per_day = round(item.views / divisor, 2)
    er = engagement_rate(item.likes, item.comments, item.views)

    sorted_history = sorted(item.history, key=lambda point: point.captured_at)
    velocity: Optional[float] = None
    acceleration: Optional[float] = None
    trend = Trend.INSUFFICIENT_DATA

    if len(sorted_history) >= MIN_HISTORY_FOR_VELOCITY:
        velocity = round(_interval_velocity(sorted_history[-1], sorted_history[-2]), 2)
        baseline = velocity
        if len(sorted_history) >= MIN_HISTORY_FOR_ACCELERATION:
            baseline = _interval_velocity(sorted_history[-2], sorted_history[-3])
            acceleration = round(velocity - baseline, 2)

        if velocity <= 0:
            trend = Trend.DECLINING
        elif baseline and baseline > 0:
            ratio = velocity / baseline
            if ratio >= ACCELERATING_RATIO:
                trend = Trend.ACCELERATING
            elif ratio <= SLOWING_RATIO:
                trend = Trend.SLOWING
            else:
                trend = Trend.STEADY
        else:
            trend = Trend.STEADY

    return DerivedItem(
        id=item.id,
        platform=item.platform,
        title=item.title,
        url=item.url,
        thumbnail_url=item.thumbnail_url,
        published_at=item.published_at,
        views=item.views,
        likes=item.likes,
        comments=item.comments,
        history=item.history,
        age_days=age_days,
        views_per_day=views_per_day,
        engagement_rate=er,
        velocity=velocity,
        acceleration=acceleration,
        trend=trend,
    )


def gained_since(item: ContentItem, now: datetime, window_days: int) -> Optional[int]:
    """Views gained since the closest snapshot at or before (now - window_days). None if no snapshot reaches back that far."""
    target = now - timedelta(days=window_days)
    sorted_history = sorted(item.history, key=lambda point: point.captured_at)
    if not sorted_history:
        return None
    latest = sorted_history[-1]
    baseline = None
    for point in sorted_history:
        if ensure_aware(point.captured_at) <= target:
            baseline = point
        else:
            break
    if baseline is None:
        return None
    return latest.views - baseline.views


def peak_growth_day(item: ContentItem) -> Optional[tuple[date, int]]:
    """The inter-snapshot interval with the largest views gained, reported by the later snapshot's date."""
    sorted_history = sorted(item.history, key=lambda point: point.captured_at)
    if len(sorted_history) < 2:
        return None
    best_gain = None
    best_date = None
    for earlier, later in zip(sorted_history, sorted_history[1:]):
        gain = later.views - earlier.views
        if best_gain is None or gain > best_gain:
            best_gain = gain
            best_date = ensure_aware(later.captured_at).date()
    if best_date is None or best_gain is None:
        return None
    return best_date, best_gain


def largest_slowdown_interval(item: ContentItem) -> Optional[tuple[date, int]]:
    """The inter-snapshot interval with the smallest (most negative) views gained —
    the mirror of peak_growth_day, used to surface a video's worst growth interval."""
    sorted_history = sorted(item.history, key=lambda point: point.captured_at)
    if len(sorted_history) < 2:
        return None
    worst_gain = None
    worst_date = None
    for earlier, later in zip(sorted_history, sorted_history[1:]):
        gain = later.views - earlier.views
        if worst_gain is None or gain < worst_gain:
            worst_gain = gain
            worst_date = ensure_aware(later.captured_at).date()
    if worst_date is None or worst_gain is None:
        return None
    return worst_date, worst_gain


@dataclass
class HistoryBucket:
    label: str
    period_start: datetime
    period_end: datetime
    views: int
    likes: int
    comments: int


# Age thresholds match the creator-facing chart rule: a video's own age decides how
# its history is grouped, never the raw cadence of synchronization runs.
DAILY_BUCKET_MAX_AGE_DAYS = 30
WEEKLY_BUCKET_MAX_AGE_DAYS = 180


def bucket_history(history: Sequence[SnapshotPoint], anchor: datetime, now: Optional[datetime] = None) -> dict:
    """Aggregate raw snapshots into creator-meaningful periods anchored to `anchor`
    (a video's publish date) instead of raw synchronization timestamps:
    - age < 30 days  -> one bucket per day since publish ("Dzień N")
    - 30-180 days    -> one bucket per week since publish ("Tydz. N")
    - > 180 days     -> one bucket per month since publish ("Mies. N")
    Cumulative counters (views/likes/comments) use the LAST snapshot seen in each
    period as that period's value, like a closing price. Returns a dict with
    `granularity`, `buckets` (list[HistoryBucket]), and `insufficient` (True when
    fewer than 2 buckets exist — a single point can't show a trend, so the caller
    should show an explanatory card instead of a chart)."""
    now = now or datetime.now(timezone.utc)
    anchor = ensure_aware(anchor)
    sorted_history = sorted(history, key=lambda point: ensure_aware(point.captured_at))
    if not sorted_history:
        return {"granularity": "daily", "buckets": [], "insufficient": True}

    age_days = max(0, (now - anchor).days)
    if age_days < DAILY_BUCKET_MAX_AGE_DAYS:
        granularity, period_days, label_prefix = "daily", 1, "Dzień"
    elif age_days <= WEEKLY_BUCKET_MAX_AGE_DAYS:
        granularity, period_days, label_prefix = "weekly", 7, "Tydz."
    else:
        granularity, period_days, label_prefix = "monthly", 30, "Mies."

    grouped: dict[int, SnapshotPoint] = {}
    for point in sorted_history:
        captured_at = ensure_aware(point.captured_at)
        period_index = max(0, (captured_at - anchor).days) // period_days
        existing = grouped.get(period_index)
        if existing is None or captured_at >= ensure_aware(existing.captured_at):
            grouped[period_index] = point

    buckets = [
        HistoryBucket(
            label=f"{label_prefix} {index + 1}",
            period_start=anchor + timedelta(days=index * period_days),
            period_end=anchor + timedelta(days=(index + 1) * period_days),
            views=point.views,
            likes=point.likes,
            comments=point.comments,
        )
        for index, point in sorted(grouped.items())
    ]
    return {"granularity": granularity, "buckets": buckets, "insufficient": len(buckets) < 2}


def median_or_none(values: Sequence[float]) -> Optional[float]:
    values = list(values)
    if not values:
        return None
    return _median(values)


def value_series_gained_since(series: Sequence[tuple[datetime, int]], now: datetime, window_days: int) -> Optional[int]:
    """Generic (captured_at, value) version of gained_since — used for channel-level
    series (e.g. subscriber count) that aren't shaped like ContentItem history."""
    if not series:
        return None
    sorted_series = sorted(series, key=lambda pair: pair[0])
    latest = sorted_series[-1]
    target = now - timedelta(days=window_days)
    baseline = None
    for captured_at, value in sorted_series:
        if ensure_aware(captured_at) <= target:
            baseline = (captured_at, value)
        else:
            break
    if baseline is None:
        return None
    return latest[1] - baseline[1]


def compute_confidence(sample_size: int, effect_size_pct: float) -> Optional[Confidence]:
    """Deterministic confidence gate reused by every recommendation category.
    Below the minimum sample size or effect size, a candidate is not surfaced at all."""
    effect = abs(effect_size_pct)
    if sample_size < 2 or effect < 15:
        return None
    if sample_size >= 5 and effect >= 25:
        return Confidence.HIGH
    if sample_size >= 3 and effect >= 15:
        return Confidence.MEDIUM
    return Confidence.LOW


# ---------------------------------------------------------------------------
# Composite score, categories & performance labels — Sprint 5
# ---------------------------------------------------------------------------


def min_max_normalize(value: float, minimum: float, maximum: float) -> float:
    if maximum == minimum:
        return 100.0
    return (value - minimum) / (maximum - minimum) * 100


def compute_composite_scores(items: list[DerivedItem]) -> dict[str, float]:
    """50% normalized views/day + 30% normalized engagement + 20% normalized views,
    min-max normalized across the given set. Mirrors the frontend's
    lib/youtube-metrics.ts formula exactly so both layers agree — relative to
    whichever set of items is passed in, never a universal/permanent score."""
    if not items:
        return {}
    views_range = (min(item.views for item in items), max(item.views for item in items))
    vpd_range = (min(item.views_per_day for item in items), max(item.views_per_day for item in items))
    er_range = (min(item.engagement_rate for item in items), max(item.engagement_rate for item in items))

    scores: dict[str, float] = {}
    for item in items:
        views_score = min_max_normalize(item.views, *views_range)
        vpd_score = min_max_normalize(item.views_per_day, *vpd_range)
        er_score = min_max_normalize(item.engagement_rate, *er_range)
        scores[item.id] = round(vpd_score * 0.5 + er_score * 0.3 + views_score * 0.2, 2)
    return scores


def engagement_category(engagement_rate_value: float) -> str:
    """Deterministic bucket for engagement rate — part of the AI-ready structured metadata (Part 8)."""
    if engagement_rate_value >= 8:
        return "excellent"
    if engagement_rate_value >= 4:
        return "good"
    if engagement_rate_value >= 1.5:
        return "average"
    return "low"


def growth_category(trend: Trend) -> str:
    """Maps the trend enum to a human-facing growth bucket — part of the AI-ready structured metadata (Part 8)."""
    return {
        Trend.ACCELERATING: "accelerating",
        Trend.STEADY: "growing",
        Trend.SLOWING: "slowing",
        Trend.DECLINING: "declining",
        Trend.INSUFFICIENT_DATA: "unknown",
    }[trend]


PERFORMANCE_LABELS: dict[str, dict[str, str]] = {
    "viral": {"emoji": "🔥", "text": "Viral"},
    "accelerating": {"emoji": "⚡", "text": "Przyspiesza"},
    "growing": {"emoji": "📈", "text": "Rośnie"},
    "strong": {"emoji": "✅", "text": "Silny"},
    "average": {"emoji": "➖", "text": "Przeciętny"},
    "weak": {"emoji": "⚠", "text": "Słaby"},
    "dead": {"emoji": "💀", "text": "Wygasł"},
}


def performance_label(item: DerivedItem, score: float, channel_median_views_per_day: float) -> str:
    """Deterministic label key (see PERFORMANCE_LABELS for emoji/text) — checked in
    priority order so a video is never tagged as two contradictory states at once."""
    is_old_enough_to_judge = item.age_days > 30

    if score >= 85 and channel_median_views_per_day > 0 and item.views_per_day >= channel_median_views_per_day * 3:
        return "viral"
    if (
        is_old_enough_to_judge
        and item.trend == Trend.DECLINING
        and channel_median_views_per_day > 0
        and item.views_per_day < channel_median_views_per_day * 0.15
    ):
        return "dead"
    if item.trend == Trend.ACCELERATING:
        return "accelerating"
    if item.trend == Trend.STEADY and (item.velocity or 0) > 0:
        return "growing"
    if score >= 70:
        return "strong"
    if score >= 40:
        return "average"
    return "weak"
