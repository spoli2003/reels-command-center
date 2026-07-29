"""Creator Intelligence orchestrator. Platform-agnostic: every function here takes
list[DerivedItem] (plus a plain (captured_at, value) series for channel-level
figures like subscriber count) and returns typed, explainable results. Nothing
imports a YouTube model — a future platform adapter feeds this the same shapes.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .content_metrics import compute_confidence, ensure_aware, gained_since, median_or_none, value_series_gained_since
from .title_patterns import TITLE_PATTERN_DETECTORS, TITLE_PATTERN_LABELS
from .topics import TopicSummary, cluster_topics
from .types import Confidence, DerivedItem, Recommendation, Trend

RECENT_COHORT_DAYS = 30
TOO_NEW_DAYS = 3
MIN_COMPARABLE = 3
ATTENTION_LIMIT = 5
NO_UPLOAD_THRESHOLD_DAYS = 4
MIN_WEEKDAY_SAMPLE = 2
MIN_HOUR_SAMPLE = 2
STREAK_GAP_DAYS = 3

WEEKDAY_LABELS_PL = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]


# ---------------------------------------------------------------------------
# Daily brief (Part 3)
# ---------------------------------------------------------------------------


@dataclass
class DailyBrief:
    views_gained_24h: Optional[int] = None
    subscribers_gained_24h: Optional[int] = None
    best_growing_video_id: Optional[str] = None
    best_growing_video_gain: Optional[int] = None
    biggest_slowdown_video_id: Optional[str] = None
    biggest_slowdown_delta: Optional[float] = None
    attention_video_ids: list[str] = field(default_factory=list)
    days_since_last_upload: Optional[int] = None
    no_upload_warning: Optional[str] = None


def daily_brief(
    items: list[DerivedItem],
    now: datetime,
    subscriber_history: Optional[list[tuple[datetime, int]]] = None,
    attention_video_ids: Optional[list[str]] = None,
) -> DailyBrief:
    gains = [(item, gained_since(item, now, 1)) for item in items]
    gains = [(item, gain) for item, gain in gains if gain is not None]
    views_gained_24h = sum(gain for _, gain in gains) if gains else None
    best_growing_video_id = best_growing_video_gain = None
    if gains:
        item, gain = max(gains, key=lambda pair: pair[1])
        best_growing_video_id, best_growing_video_gain = item.id, gain

    accel_candidates = [item for item in items if item.acceleration is not None]
    biggest_slowdown_video_id = biggest_slowdown_delta = None
    if accel_candidates:
        worst = min(accel_candidates, key=lambda item: item.acceleration)
        if worst.acceleration is not None and worst.acceleration < 0:
            biggest_slowdown_video_id = worst.id
            biggest_slowdown_delta = worst.acceleration

    subscribers_gained_24h = value_series_gained_since(subscriber_history or [], now, 1)

    days_since_last_upload = None
    no_upload_warning = None
    if items:
        latest_published = max(ensure_aware(item.published_at) for item in items)
        days_since_last_upload = (now - latest_published).days
        if days_since_last_upload >= NO_UPLOAD_THRESHOLD_DAYS:
            no_upload_warning = f"Brak nowej publikacji od {days_since_last_upload} dni."

    return DailyBrief(
        views_gained_24h=views_gained_24h,
        subscribers_gained_24h=subscribers_gained_24h,
        best_growing_video_id=best_growing_video_id,
        best_growing_video_gain=best_growing_video_gain,
        biggest_slowdown_video_id=biggest_slowdown_video_id,
        biggest_slowdown_delta=biggest_slowdown_delta,
        attention_video_ids=attention_video_ids or [],
        days_since_last_upload=days_since_last_upload,
        no_upload_warning=no_upload_warning,
    )


# ---------------------------------------------------------------------------
# Winning videos (Part 4)
# ---------------------------------------------------------------------------


def winning_videos(items: list[DerivedItem]) -> list[Recommendation]:
    if not items:
        return []
    small_cohort = len(items) < 3
    base_confidence = Confidence.LOW if small_cohort else Confidence.HIGH
    recommendations: list[Recommendation] = []

    by_vpd = max(items, key=lambda i: i.views_per_day)
    recommendations.append(
        Recommendation(
            id=f"winning_views_per_day:{by_vpd.id}",
            category="winning",
            headline=f"Najwyższe wyświetlenia/dzień: „{by_vpd.title}”",
            explanation=f"{by_vpd.views_per_day:.0f} wyświetleń/dzień — najwyższy wynik wśród {len(items)} analizowanych filmów.",
            confidence=base_confidence,
            supporting_metrics={"views_per_day": by_vpd.views_per_day, "sample_size": len(items)},
            supporting_video_ids=[by_vpd.id],
        )
    )

    by_er = max(items, key=lambda i: i.engagement_rate)
    recommendations.append(
        Recommendation(
            id=f"winning_engagement:{by_er.id}",
            category="winning",
            headline=f"Najwyższy engagement: „{by_er.title}”",
            explanation=f"Engagement {by_er.engagement_rate:.2f}% — najwyższy wynik wśród {len(items)} analizowanych filmów.",
            confidence=base_confidence,
            supporting_metrics={"engagement_rate": by_er.engagement_rate, "sample_size": len(items)},
            supporting_video_ids=[by_er.id],
        )
    )

    velocity_candidates = [i for i in items if i.velocity is not None]
    if velocity_candidates:
        fastest = max(velocity_candidates, key=lambda i: i.velocity)
        if fastest.velocity and fastest.velocity > 0:
            recommendations.append(
                Recommendation(
                    id=f"winning_fastest_growing:{fastest.id}",
                    category="winning",
                    headline=f"Najszybciej rosnący: „{fastest.title}”",
                    explanation=f"Tempo wzrostu {fastest.velocity:.0f} wyświetleń/dzień między ostatnimi dwiema synchronizacjami.",
                    confidence=base_confidence,
                    supporting_metrics={"velocity_views_per_day": fastest.velocity},
                    supporting_video_ids=[fastest.id],
                )
            )

    still_growing = [
        i for i in items if i.age_days >= 30 and i.trend in (Trend.ACCELERATING, Trend.STEADY) and (i.velocity or 0) > 0
    ]
    if still_growing:
        best_still_growing = max(still_growing, key=lambda i: i.velocity or 0)
        recommendations.append(
            Recommendation(
                id=f"winning_still_growing:{best_still_growing.id}",
                category="winning",
                headline=f"Wciąż rośnie po 30+ dniach: „{best_still_growing.title}”",
                explanation=f"Film ma {best_still_growing.age_days} dni i wciąż zyskuje ok. {best_still_growing.velocity:.0f} wyświetleń/dzień.",
                confidence=base_confidence,
                supporting_metrics={"age_days": best_still_growing.age_days, "velocity_views_per_day": best_still_growing.velocity},
                supporting_video_ids=[best_still_growing.id],
            )
        )

    recent = [i for i in items if i.age_days <= RECENT_COHORT_DAYS]
    if len(recent) >= 2:
        best_recent = max(recent, key=lambda i: i.views_per_day)
        recommendations.append(
            Recommendation(
                id=f"winning_best_recent:{best_recent.id}",
                category="winning",
                headline=f"Najlepszy ostatni upload: „{best_recent.title}”",
                explanation=(
                    f"Wśród {len(recent)} filmów opublikowanych w ciągu ostatnich {RECENT_COHORT_DAYS} dni ten ma "
                    f"najwyższe wyświetlenia/dzień ({best_recent.views_per_day:.0f})."
                ),
                confidence=base_confidence,
                supporting_metrics={"views_per_day": best_recent.views_per_day, "cohort_size": len(recent)},
                supporting_video_ids=[best_recent.id],
            )
        )

    return recommendations


# ---------------------------------------------------------------------------
# Attention videos (Part 5)
# ---------------------------------------------------------------------------


def too_new_count(items: list[DerivedItem]) -> int:
    return sum(1 for item in items if item.age_days < TOO_NEW_DAYS)


def attention_videos(items: list[DerivedItem]) -> list[Recommendation]:
    comparable = [item for item in items if item.age_days >= TOO_NEW_DAYS]
    if len(comparable) < MIN_COMPARABLE:
        return []
    median_vpd = median_or_none([item.views_per_day for item in comparable]) or 0
    median_er = median_or_none([item.engagement_rate for item in comparable]) or 0

    flagged: list[Recommendation] = []
    for item in comparable:
        reasons: list[str] = []
        metrics: dict = {}
        if median_vpd > 0 and item.views_per_day <= median_vpd * 0.7:
            pct = round((1 - item.views_per_day / median_vpd) * 100)
            reasons.append(f"Wyświetlenia/dzień są o {pct}% niższe od mediany kanału ({item.views_per_day:.0f} vs {median_vpd:.0f}).")
            metrics["views_per_day"] = item.views_per_day
            metrics["median_views_per_day"] = median_vpd
        if median_er > 0 and item.engagement_rate <= median_er * 0.5 and item.views_per_day > median_vpd * 0.7:
            reasons.append(f"Słaby poziom reakcji (ER {item.engagement_rate:.2f}% vs mediana {median_er:.2f}%).")
            metrics["engagement_rate"] = item.engagement_rate
            metrics["median_engagement_rate"] = median_er
        if item.trend == Trend.DECLINING and item.age_days > RECENT_COHORT_DAYS:
            reasons.append("Wzrost zatrzymał się — brak przyrostu wyświetleń między ostatnimi synchronizacjami.")
        if reasons:
            flagged.append(
                Recommendation(
                    id=f"attention:{item.id}",
                    category="attention",
                    headline=f"Wymaga uwagi: „{item.title}”",
                    explanation=" ".join(reasons),
                    confidence=Confidence.MEDIUM,
                    supporting_metrics=metrics,
                    supporting_video_ids=[item.id],
                )
            )
    flagged.sort(key=lambda rec: rec.supporting_metrics.get("views_per_day", 0))
    return flagged[:ATTENTION_LIMIT]


# ---------------------------------------------------------------------------
# Publishing intelligence (Part 7)
# ---------------------------------------------------------------------------


@dataclass
class PublishingInsight:
    best_weekday: Optional[str] = None
    best_weekday_median_vpd: Optional[float] = None
    best_hour: Optional[int] = None
    best_hour_median_vpd: Optional[float] = None
    best_cadence_label: Optional[str] = None
    best_cadence_median_vpd: Optional[float] = None
    best_streak_start: Optional[str] = None
    best_streak_end: Optional[str] = None
    best_streak_video_count: Optional[int] = None
    best_streak_avg_vpd: Optional[float] = None
    worst_streak_start: Optional[str] = None
    worst_streak_end: Optional[str] = None
    worst_streak_video_count: Optional[int] = None
    worst_streak_avg_vpd: Optional[float] = None
    insufficient_data_notes: list[str] = field(default_factory=list)


def _cadence_bucket(gap_days: float) -> str:
    if gap_days <= 1.5:
        return "codziennie"
    if gap_days <= 3.5:
        return "co 2-3 dni"
    if gap_days <= 8:
        return "co tydzień"
    return "rzadziej niż co tydzień"


def publishing_intelligence(items: list[DerivedItem]) -> PublishingInsight:
    result = PublishingInsight()
    if len(items) < 2:
        result.insufficient_data_notes.append("Za mało filmów, aby analizować wzorce publikacji.")
        return result

    weekday_buckets: dict[int, list[float]] = {}
    hour_buckets: dict[int, list[float]] = {}
    for item in items:
        published = ensure_aware(item.published_at)
        weekday_buckets.setdefault(published.weekday(), []).append(item.views_per_day)
        hour_buckets.setdefault(published.hour, []).append(item.views_per_day)

    eligible_weekdays = {day: vals for day, vals in weekday_buckets.items() if len(vals) >= MIN_WEEKDAY_SAMPLE}
    if eligible_weekdays:
        best_day, best_vals = max(eligible_weekdays.items(), key=lambda pair: median_or_none(pair[1]) or 0)
        result.best_weekday = WEEKDAY_LABELS_PL[best_day]
        result.best_weekday_median_vpd = median_or_none(best_vals)
    else:
        result.insufficient_data_notes.append(f"Za mało filmów na jeden dzień tygodnia (min. {MIN_WEEKDAY_SAMPLE}), aby wskazać najlepszy dzień.")

    eligible_hours = {hour: vals for hour, vals in hour_buckets.items() if len(vals) >= MIN_HOUR_SAMPLE}
    if eligible_hours:
        best_hour, best_hour_vals = max(eligible_hours.items(), key=lambda pair: median_or_none(pair[1]) or 0)
        result.best_hour = best_hour
        result.best_hour_median_vpd = median_or_none(best_hour_vals)
    else:
        result.insufficient_data_notes.append(f"Za mało filmów o tej samej godzinie publikacji (min. {MIN_HOUR_SAMPLE}), aby wskazać najlepszą godzinę.")

    sorted_items = sorted(items, key=lambda i: i.published_at)
    gaps: list[tuple[float, DerivedItem]] = []
    for earlier, later in zip(sorted_items, sorted_items[1:]):
        gap_days = (ensure_aware(later.published_at) - ensure_aware(earlier.published_at)).total_seconds() / 86400
        gaps.append((gap_days, later))

    cadence_buckets: dict[str, list[float]] = {}
    for gap_days, later_item in gaps:
        cadence_buckets.setdefault(_cadence_bucket(gap_days), []).append(later_item.views_per_day)
    eligible_cadence = {label: vals for label, vals in cadence_buckets.items() if len(vals) >= MIN_WEEKDAY_SAMPLE}
    if eligible_cadence:
        best_label, best_cadence_vals = max(eligible_cadence.items(), key=lambda pair: median_or_none(pair[1]) or 0)
        result.best_cadence_label = best_label
        result.best_cadence_median_vpd = median_or_none(best_cadence_vals)
    else:
        result.insufficient_data_notes.append("Za mało danych, aby wskazać najlepszą częstotliwość publikacji.")

    streaks: list[list[DerivedItem]] = []
    current_streak = [sorted_items[0]] if sorted_items else []
    for gap_days, later_item in gaps:
        if gap_days <= STREAK_GAP_DAYS:
            current_streak.append(later_item)
        else:
            if len(current_streak) >= 2:
                streaks.append(current_streak)
            current_streak = [later_item]
    if len(current_streak) >= 2:
        streaks.append(current_streak)

    if streaks:
        def _streak_avg(streak: list[DerivedItem]) -> float:
            return median_or_none([i.views_per_day for i in streak]) or 0

        best_streak = max(streaks, key=_streak_avg)
        worst_streak = min(streaks, key=_streak_avg)
        result.best_streak_start = ensure_aware(best_streak[0].published_at).date().isoformat()
        result.best_streak_end = ensure_aware(best_streak[-1].published_at).date().isoformat()
        result.best_streak_video_count = len(best_streak)
        result.best_streak_avg_vpd = _streak_avg(best_streak)
        if worst_streak is not best_streak:
            result.worst_streak_start = ensure_aware(worst_streak[0].published_at).date().isoformat()
            result.worst_streak_end = ensure_aware(worst_streak[-1].published_at).date().isoformat()
            result.worst_streak_video_count = len(worst_streak)
            result.worst_streak_avg_vpd = _streak_avg(worst_streak)
    else:
        result.insufficient_data_notes.append(f"Za mało serii kolejnych publikacji (odstęp ≤{STREAK_GAP_DAYS} dni), aby wskazać najlepszy/najgorszy okres.")

    return result


# ---------------------------------------------------------------------------
# Follow-up opportunities (Part 8)
# ---------------------------------------------------------------------------


def follow_up_opportunities(items: list[DerivedItem], topics: list[TopicSummary], limit: int = 3) -> list[Recommendation]:
    if len(items) < MIN_COMPARABLE:
        return []
    median_vpd = median_or_none([item.views_per_day for item in items]) or 0
    if median_vpd <= 0:
        return []

    topic_by_video: dict[str, TopicSummary] = {}
    for topic in topics:
        for video_id in topic.supporting_video_ids:
            existing = topic_by_video.get(video_id)
            if existing is None or topic.video_count > existing.video_count:
                topic_by_video[video_id] = topic

    candidates = sorted(items, key=lambda i: i.views_per_day, reverse=True)[: max(limit * 2, 5)]
    recommendations: list[Recommendation] = []
    for item in candidates:
        if item.views_per_day <= median_vpd * 1.15:
            continue
        pct = round((item.views_per_day / median_vpd - 1) * 100)
        topic = topic_by_video.get(item.id)
        topic_note = (
            f" Należy też do tematu „{topic.keyword}” ({topic.video_count} filmów, mediana {topic.median_views_per_day:.0f} wyśw./dzień)."
            if topic
            else ""
        )
        recommendations.append(
            Recommendation(
                id=f"follow_up:{item.id}",
                category="follow_up",
                headline=f"Rozważ kontynuację: „{item.title}”",
                explanation=(
                    f"Ten film należy do najlepszych wyników kanału — {item.views_per_day:.0f} wyświetleń/dzień, "
                    f"o {pct}% powyżej mediany kanału ({median_vpd:.0f}).{topic_note} "
                    "Możliwe formy kontynuacji: część 2, aktualizacja, FAQ, najczęstsze błędy — wybór formy zależy od Ciebie."
                ),
                confidence=compute_confidence(2, pct) or Confidence.LOW,
                supporting_metrics={"views_per_day": item.views_per_day, "channel_median_views_per_day": median_vpd, "percent_above_median": pct},
                supporting_video_ids=[item.id],
            )
        )
        if len(recommendations) >= limit:
            break
    return recommendations


# ---------------------------------------------------------------------------
# Title intelligence (Part 9)
# ---------------------------------------------------------------------------


def title_intelligence(items: list[DerivedItem]) -> list[Recommendation]:
    if len(items) < MIN_COMPARABLE:
        return []
    recommendations: list[Recommendation] = []
    for pattern_key, detector in TITLE_PATTERN_DETECTORS.items():
        with_pattern = [item for item in items if detector(item.title)]
        without_pattern = [item for item in items if not detector(item.title)]
        if len(with_pattern) < 2 or not without_pattern:
            continue
        median_with = median_or_none([item.views_per_day for item in with_pattern]) or 0
        median_without = median_or_none([item.views_per_day for item in without_pattern]) or 0
        if median_without <= 0:
            continue
        pct = round((median_with / median_without - 1) * 100)
        confidence = compute_confidence(len(with_pattern), pct)
        if confidence is None:
            continue
        label = TITLE_PATTERN_LABELS[pattern_key]
        direction = "wyższą" if pct > 0 else "niższą"
        recommendations.append(
            Recommendation(
                id=f"title_pattern:{pattern_key}",
                category="title_pattern",
                headline=f"{label}: {'wyższe' if pct > 0 else 'niższe'} wyniki",
                explanation=(
                    f"Na podstawie Twoich dotychczasowych danych: filmy z tytułami pasującymi do tego wzorca ({len(with_pattern)} filmów) "
                    f"mają medianę wyświetleń/dzień o {abs(pct)}% {direction} niż pozostałe ({median_with:.0f} vs {median_without:.0f})."
                ),
                confidence=confidence,
                supporting_metrics={
                    "median_views_per_day_with": median_with,
                    "median_views_per_day_without": median_without,
                    "sample_size": len(with_pattern),
                    "percent_diff": pct,
                },
                supporting_video_ids=[item.id for item in with_pattern[:5]],
            )
        )
    return recommendations


# ---------------------------------------------------------------------------
# Content recommendations — synthesis layer (Part 10)
# ---------------------------------------------------------------------------


def content_recommendations(items: list[DerivedItem], topics: list[TopicSummary], limit: int = 5) -> list[Recommendation]:
    if len(items) < MIN_COMPARABLE:
        return []
    channel_median_vpd = median_or_none([item.views_per_day for item in items]) or 0
    recommendations: list[Recommendation] = []

    if channel_median_vpd > 0:
        for topic in topics:
            pct = round((topic.median_views_per_day / channel_median_vpd - 1) * 100)
            confidence = compute_confidence(topic.video_count, pct)
            if confidence is None:
                continue
            direction = "powyżej" if pct > 0 else "poniżej"
            recommendations.append(
                Recommendation(
                    id=f"content_topic:{topic.keyword}",
                    category="content",
                    headline=f"Temat „{topic.keyword}” {direction} mediany kanału",
                    explanation=(
                        f"Na podstawie Twoich dotychczasowych danych: filmy zawierające słowo „{topic.keyword}” ({topic.video_count} filmów) "
                        f"mają medianę wyświetleń/dzień o {abs(pct)}% {direction} mediany kanału "
                        f"({topic.median_views_per_day:.0f} vs {channel_median_vpd:.0f})."
                    ),
                    confidence=confidence,
                    supporting_metrics={
                        "topic_median_views_per_day": topic.median_views_per_day,
                        "channel_median_views_per_day": channel_median_vpd,
                        "percent_diff": pct,
                        "sample_size": topic.video_count,
                    },
                    supporting_video_ids=topic.supporting_video_ids[:5],
                )
            )

    top_10 = sorted(items, key=lambda i: i.views_per_day, reverse=True)[:10]
    top_10_ids = {item.id for item in top_10}
    for topic in topics:
        overlap = [video_id for video_id in topic.supporting_video_ids if video_id in top_10_ids]
        if len(overlap) >= 3:
            recommendations.append(
                Recommendation(
                    id=f"content_keyword_top10:{topic.keyword}",
                    category="content",
                    headline=f"Słowo „{topic.keyword}” dominuje w najlepszych wynikach",
                    explanation=(
                        f"Na podstawie Twoich dotychczasowych danych: słowo „{topic.keyword}” pojawia się w {len(overlap)} "
                        f"z {len(top_10)} najlepszych filmów kanału (wg wyświetleń/dzień)."
                    ),
                    confidence=Confidence.MEDIUM if len(overlap) < 5 else Confidence.HIGH,
                    supporting_metrics={"overlap_count": len(overlap), "top_n": len(top_10)},
                    supporting_video_ids=overlap,
                )
            )

    topic_velocities: list[tuple[TopicSummary, float]] = []
    for topic in topics:
        members_with_velocity = [item for item in items if item.id in topic.supporting_video_ids and item.velocity is not None]
        if len(members_with_velocity) >= 2:
            avg_velocity = sum(item.velocity for item in members_with_velocity) / len(members_with_velocity)
            topic_velocities.append((topic, avg_velocity))
    if len(topic_velocities) >= 2:
        topic_velocities.sort(key=lambda pair: pair[1], reverse=True)
        fastest_topic, fastest_v = topic_velocities[0]
        slowest_topic, slowest_v = topic_velocities[-1]
        if fastest_topic is not slowest_topic and slowest_v != 0 and abs((fastest_v - slowest_v) / abs(slowest_v)) * 100 >= 15:
            recommendations.append(
                Recommendation(
                    id=f"content_velocity_compare:{fastest_topic.keyword}:{slowest_topic.keyword}",
                    category="content",
                    headline=f"„{fastest_topic.keyword}” przyspiesza szybciej niż „{slowest_topic.keyword}”",
                    explanation=(
                        f"Na podstawie Twoich dotychczasowych danych: filmy o temacie „{fastest_topic.keyword}” zyskują średnio "
                        f"{fastest_v:.0f} wyświetleń/dzień między synchronizacjami, wobec {slowest_v:.0f} dla tematu „{slowest_topic.keyword}”."
                    ),
                    confidence=Confidence.LOW,
                    supporting_metrics={"fastest_topic_velocity": fastest_v, "slowest_topic_velocity": slowest_v},
                    supporting_video_ids=(fastest_topic.supporting_video_ids[:3] + slowest_topic.supporting_video_ids[:3]),
                )
            )

    return recommendations[:limit]


# ---------------------------------------------------------------------------
# Top-level report
# ---------------------------------------------------------------------------


@dataclass
class IntelligenceReport:
    daily_brief: DailyBrief
    winning_videos: list[Recommendation]
    attention_videos: list[Recommendation]
    too_new_count: int
    topics: list[TopicSummary]
    publishing: PublishingInsight
    follow_up_opportunities: list[Recommendation]
    title_patterns: list[Recommendation]
    content_recommendations: list[Recommendation]


def build_intelligence_report(
    items: list[DerivedItem],
    now: datetime,
    subscriber_history: Optional[list[tuple[datetime, int]]] = None,
) -> IntelligenceReport:
    attention = attention_videos(items)
    topics = cluster_topics(items)
    brief = daily_brief(
        items,
        now,
        subscriber_history=subscriber_history,
        attention_video_ids=[rec.supporting_video_ids[0] for rec in attention if rec.supporting_video_ids],
    )
    return IntelligenceReport(
        daily_brief=brief,
        winning_videos=winning_videos(items),
        attention_videos=attention,
        too_new_count=too_new_count(items),
        topics=topics,
        publishing=publishing_intelligence(items),
        follow_up_opportunities=follow_up_opportunities(items, topics),
        title_patterns=title_intelligence(items),
        content_recommendations=content_recommendations(items, topics),
    )
