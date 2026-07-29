"""Pure-engine tests for the Creator Intelligence package. No database, no
YouTube-specific types — this is exactly what makes the engine reusable for a
future Facebook/Instagram/TikTok platform."""

from datetime import datetime, timedelta, timezone

from app.services.intelligence.content_metrics import (
    bucket_history,
    compute_composite_scores,
    compute_confidence,
    derive,
    engagement_category,
    gained_since,
    growth_category,
    largest_slowdown_interval,
    median_or_none,
    peak_growth_day,
    performance_label,
    PERFORMANCE_LABELS,
)
from app.services.intelligence.engine import (
    attention_videos,
    build_intelligence_report,
    daily_brief,
    follow_up_opportunities,
    publishing_intelligence,
    too_new_count,
    winning_videos,
)
from app.services.intelligence.title_patterns import has_number, has_question
from app.services.intelligence.topics import cluster_topics, stem_word, tokenize_title
from app.services.intelligence.types import Confidence, ContentItem, SnapshotPoint, Trend

NOW = datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc)


def _item(id_, title, published_days_ago, views, likes=0, comments=0, history=None):
    return ContentItem(
        id=id_,
        platform="youtube",
        title=title,
        url=None,
        thumbnail_url=None,
        published_at=NOW - timedelta(days=published_days_ago),
        views=views,
        likes=likes,
        comments=comments,
        history=history or [],
    )


def test_derive_computes_views_per_day_and_engagement():
    derived = derive(_item("a", "Test", 10, 1000, likes=50, comments=10), now=NOW)
    assert derived.age_days == 10
    assert derived.views_per_day == 100.0
    assert derived.engagement_rate == 6.0


def test_derive_trend_accelerating():
    history = [
        SnapshotPoint(NOW - timedelta(days=4), 100, 0, 0),
        SnapshotPoint(NOW - timedelta(days=2), 200, 0, 0),  # velocity 50/day
        SnapshotPoint(NOW, 400, 0, 0),  # velocity 100/day -> ratio 2.0
    ]
    derived = derive(_item("a", "Test", 10, 400, history=history), now=NOW)
    assert derived.velocity == 100.0
    assert derived.trend == Trend.ACCELERATING


def test_derive_trend_declining_on_zero_growth():
    history = [SnapshotPoint(NOW - timedelta(days=2), 100, 0, 0), SnapshotPoint(NOW, 100, 0, 0)]
    derived = derive(_item("a", "Test", 10, 100, history=history), now=NOW)
    assert derived.velocity == 0.0
    assert derived.trend == Trend.DECLINING


def test_derive_insufficient_history():
    derived = derive(_item("a", "Test", 10, 100, history=[SnapshotPoint(NOW, 100, 0, 0)]), now=NOW)
    assert derived.velocity is None
    assert derived.trend == Trend.INSUFFICIENT_DATA


def test_gained_since_uses_closest_prior_snapshot():
    history = [
        SnapshotPoint(NOW - timedelta(days=10), 100, 0, 0),
        SnapshotPoint(NOW - timedelta(days=2), 300, 0, 0),
        SnapshotPoint(NOW, 500, 0, 0),
    ]
    item = _item("a", "Test", 10, 500, history=history)
    assert gained_since(item, NOW, 7) == 500 - 100
    assert gained_since(item, NOW, 1) == 500 - 300


def test_gained_since_none_when_no_history_reaches_back():
    item = _item("a", "Test", 1, 100, history=[SnapshotPoint(NOW - timedelta(hours=1), 100, 0, 0)])
    assert gained_since(item, NOW, 30) is None


def test_compute_confidence_thresholds():
    assert compute_confidence(1, 50) is None
    assert compute_confidence(5, 10) is None
    assert compute_confidence(2, 20) == Confidence.LOW
    assert compute_confidence(3, 16) == Confidence.MEDIUM
    assert compute_confidence(5, 30) == Confidence.HIGH


def test_median_or_none():
    assert median_or_none([]) is None
    assert median_or_none([1, 2, 3]) == 2


def test_tokenize_title_filters_stopwords_and_short_words():
    tokens = tokenize_title("Czy możesz nagrywać wypadek przy pracy w kopalni?")
    assert "wypadek" in tokens
    assert "kopalni" in tokens
    assert "przy" not in tokens
    assert "czy" not in tokens


def test_stem_word_strips_common_suffixes():
    assert stem_word("filmami") == "film"
    assert stem_word("praca") == "prac"
    assert stem_word("test") == "test"  # too short to strip (4-1=3 < MIN_STEM_LENGTH)


def test_cluster_topics_groups_by_shared_keyword():
    items = [
        derive(_item("1", "Wypadek przy pracy w kopalni", 40, 1000), now=NOW),
        derive(_item("2", "Jak zgłosić wypadek w kopalni", 30, 2000), now=NOW),
        derive(_item("3", "Urlop wypoczynkowy zasady", 20, 500), now=NOW),
    ]
    topics = cluster_topics(items)
    keywords = {t.keyword for t in topics}
    assert keywords == {"wypadek", "kopalni"}
    assert all(t.video_count == 2 for t in topics)


def test_title_patterns_detect_question_and_number():
    assert has_question("Czy możesz nagrywać szefa?")
    assert not has_question("Wypadek przy pracy od A do Z")
    assert has_number("7 sierpnia zmiany w prawie")
    assert not has_number("Wypadek przy pracy")


def test_winning_videos_identifies_top_performer():
    items = [
        derive(_item("1", "Slaby film", 40, 100), now=NOW),
        derive(_item("2", "Dobry film", 40, 5000), now=NOW),
        derive(_item("3", "Sredni film", 40, 1000), now=NOW),
    ]
    recs = winning_videos(items)
    assert any(r.supporting_video_ids == ["2"] for r in recs if r.category == "winning")


def test_attention_videos_requires_minimum_comparable_set():
    items = [derive(_item(str(i), f"Film {i}", 10, 100), now=NOW) for i in range(2)]
    assert attention_videos(items) == []


def test_attention_videos_flags_below_median():
    items = [
        derive(_item("1", "Slaby", 10, 10), now=NOW),
        derive(_item("2", "Sredni", 10, 500), now=NOW),
        derive(_item("3", "Dobry", 10, 600), now=NOW),
        derive(_item("4", "Bardzo dobry", 10, 700), now=NOW),
    ]
    recs = attention_videos(items)
    assert any(r.supporting_video_ids == ["1"] for r in recs)


def test_attention_videos_excludes_too_new():
    items = [
        derive(_item("1", "Nowy", 1, 10), now=NOW),
        derive(_item("2", "Sredni", 10, 500), now=NOW),
        derive(_item("3", "Dobry", 10, 600), now=NOW),
        derive(_item("4", "Bardzo dobry", 10, 700), now=NOW),
    ]
    recs = attention_videos(items)
    assert not any(r.supporting_video_ids == ["1"] for r in recs)
    assert too_new_count(items) == 1


def test_daily_brief_honest_when_no_recent_history():
    items = [derive(_item("1", "Film", 10, 100), now=NOW)]
    brief = daily_brief(items, NOW)
    assert brief.views_gained_24h is None


def test_daily_brief_no_upload_warning():
    items = [derive(_item("1", "Film", 10, 100), now=NOW)]
    brief = daily_brief(items, NOW)
    assert brief.no_upload_warning is not None
    assert "10" in brief.no_upload_warning


def test_publishing_intelligence_insufficient_data():
    items = [derive(_item("1", "Film", 10, 100), now=NOW)]
    result = publishing_intelligence(items)
    assert result.best_weekday is None
    assert result.insufficient_data_notes


def test_follow_up_opportunities_requires_above_median():
    items = [derive(_item(str(i), f"Film {i}", 20, 100), now=NOW) for i in range(4)]
    items.append(derive(_item("star", "Swietny film", 20, 5000), now=NOW))
    recs = follow_up_opportunities(items, [])
    assert any(r.supporting_video_ids == ["star"] for r in recs)


def test_build_intelligence_report_end_to_end_with_synthetic_data():
    items = [derive(_item(str(i), f"Wypadek przy pracy numer {i}", 40 - i, 1000 + i * 50), now=NOW) for i in range(6)]
    report = build_intelligence_report(items, NOW)
    assert report.winning_videos
    assert report.topics
    assert isinstance(report.too_new_count, int)


# ---------------------------------------------------------------------------
# Sprint 5: composite score, categories, performance label
# ---------------------------------------------------------------------------


def test_compute_composite_scores_relative_to_set():
    items = [derive(_item("1", "Slaby", 40, 100), now=NOW), derive(_item("2", "Dobry", 40, 1000), now=NOW)]
    scores = compute_composite_scores(items)
    assert scores["2"] > scores["1"]


def test_compute_composite_scores_empty_input():
    assert compute_composite_scores([]) == {}


def test_engagement_category_thresholds():
    assert engagement_category(10) == "excellent"
    assert engagement_category(5) == "good"
    assert engagement_category(2) == "average"
    assert engagement_category(0.5) == "low"


def test_growth_category_maps_every_trend():
    assert growth_category(Trend.ACCELERATING) == "accelerating"
    assert growth_category(Trend.STEADY) == "growing"
    assert growth_category(Trend.SLOWING) == "slowing"
    assert growth_category(Trend.DECLINING) == "declining"
    assert growth_category(Trend.INSUFFICIENT_DATA) == "unknown"


def test_performance_labels_dict_covers_every_possible_output():
    possible_outputs = {"viral", "dead", "accelerating", "growing", "strong", "average", "weak"}
    assert possible_outputs == set(PERFORMANCE_LABELS.keys())


def test_performance_label_viral_requires_both_score_and_multiple():
    viral_item = derive(_item("v", "Viral", 40, 100_000), now=NOW)
    assert performance_label(viral_item, score=90, channel_median_views_per_day=100) == "viral"
    # High score alone, without the 3x-median multiple, is NOT viral.
    not_quite = derive(_item("n", "Not quite viral", 40, 250), now=NOW)
    assert performance_label(not_quite, score=90, channel_median_views_per_day=100) != "viral"


def test_performance_label_dead_requires_old_and_declining_and_far_below_median():
    history = [SnapshotPoint(NOW - timedelta(days=2), 500, 0, 0), SnapshotPoint(NOW, 500, 0, 0)]
    old_declining = derive(_item("d", "Dead", 40, 500, history=history), now=NOW)
    assert performance_label(old_declining, score=20, channel_median_views_per_day=1000) == "dead"
    # Same shape but too young to judge — must not be labeled dead.
    young_declining = derive(_item("y", "Too young", 2, 500, history=history), now=NOW)
    assert performance_label(young_declining, score=20, channel_median_views_per_day=1000) != "dead"


def test_performance_label_accelerating_and_growing():
    accel_history = [
        SnapshotPoint(NOW - timedelta(days=4), 100, 0, 0),
        SnapshotPoint(NOW - timedelta(days=2), 200, 0, 0),
        SnapshotPoint(NOW, 400, 0, 0),
    ]
    accelerating = derive(_item("a", "Accel", 10, 400, history=accel_history), now=NOW)
    assert performance_label(accelerating, score=50, channel_median_views_per_day=50) == "accelerating"

    growing_history = [SnapshotPoint(NOW - timedelta(days=2), 100, 0, 0), SnapshotPoint(NOW, 150, 0, 0)]
    growing = derive(_item("g", "Growing", 10, 150, history=growing_history), now=NOW)
    assert performance_label(growing, score=50, channel_median_views_per_day=50) == "growing"


def test_performance_label_strong_average_weak_tiers():
    strong = derive(_item("s", "Strong", 40, 500), now=NOW)
    assert performance_label(strong, score=75, channel_median_views_per_day=50) == "strong"

    average = derive(_item("m", "Mid", 40, 500), now=NOW)
    assert performance_label(average, score=50, channel_median_views_per_day=50) == "average"

    weak = derive(_item("w", "Weak", 40, 10), now=NOW)
    assert performance_label(weak, score=10, channel_median_views_per_day=50) == "weak"


# ---------------------------------------------------------------------------
# Sprint 6: history bucketing, peak growth / largest slowdown
# ---------------------------------------------------------------------------


def test_bucket_history_daily_for_young_video():
    published_at = NOW - timedelta(days=5)
    history = [
        SnapshotPoint(published_at + timedelta(days=1), 100, 0, 0),
        SnapshotPoint(published_at + timedelta(days=2), 200, 0, 0),
        SnapshotPoint(published_at + timedelta(days=3), 300, 0, 0),
    ]
    result = bucket_history(history, published_at, now=NOW)
    assert result["granularity"] == "daily"
    assert not result["insufficient"]
    assert [b.label for b in result["buckets"]] == ["Dzień 2", "Dzień 3", "Dzień 4"]


def test_bucket_history_weekly_for_mid_age_video():
    published_at = NOW - timedelta(days=60)
    history = [SnapshotPoint(published_at + timedelta(days=offset), 100 * offset, 0, 0) for offset in range(0, 40, 3)]
    result = bucket_history(history, published_at, now=NOW)
    assert result["granularity"] == "weekly"
    assert len(result["buckets"]) > 1


def test_bucket_history_monthly_for_old_video():
    published_at = NOW - timedelta(days=400)
    history = [SnapshotPoint(published_at + timedelta(days=offset), 100 * offset, 0, 0) for offset in range(0, 380, 20)]
    result = bucket_history(history, published_at, now=NOW)
    assert result["granularity"] == "monthly"
    assert len(result["buckets"]) > 1


def test_bucket_history_insufficient_when_single_bucket():
    published_at = NOW - timedelta(days=2)
    history = [SnapshotPoint(published_at + timedelta(hours=1), 100, 0, 0), SnapshotPoint(published_at + timedelta(hours=5), 150, 0, 0)]
    result = bucket_history(history, published_at, now=NOW)
    assert result["insufficient"] is True
    assert len(result["buckets"]) == 1


def test_bucket_history_empty_history():
    result = bucket_history([], NOW - timedelta(days=10), now=NOW)
    assert result["buckets"] == []
    assert result["insufficient"] is True


def test_peak_growth_day_and_largest_slowdown_are_mirrors():
    history = [
        SnapshotPoint(NOW - timedelta(days=3), 100, 0, 0),
        SnapshotPoint(NOW - timedelta(days=2), 500, 0, 0),  # +400, best
        SnapshotPoint(NOW - timedelta(days=1), 480, 0, 0),  # -20, worst
        SnapshotPoint(NOW, 600, 0, 0),
    ]
    item = _item("h", "History", 10, 600, history=history)
    peak = peak_growth_day(item)
    slowdown = largest_slowdown_interval(item)
    assert peak[1] == 400
    assert slowdown[1] == -20
