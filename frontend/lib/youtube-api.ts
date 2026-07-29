export type YoutubeSummary = {
  // last_synced_at intentionally absent — GET /status (YoutubeStatus) is the
  // single source of truth for sync time/state everywhere in the app.
  channel_title: string | null;
  subscriber_count: number;
  total_videos: number;
  total_views: number;
  total_likes: number;
  total_comments: number;
  avg_views_per_video: number;
  avg_engagement_rate: number;
  days_since_oldest_video: number | null;
  channel_views_per_day: number | null;
};

export type YoutubeStatus = {
  configured: boolean;
  connected: boolean;
  channel_title: string | null;
  channel_id: string | null;
  last_synced_at: string | null;
  video_count: number;
  message: string;
  last_sync_status: string | null;
  last_sync_duration_seconds: number | null;
  last_sync_videos_discovered: number | null;
  last_sync_videos_new: number | null;
  last_sync_videos_updated: number | null;
  last_sync_snapshots_created: number | null;
  last_sync_snapshots_deduplicated: number | null;
  last_sync_videos_failed: number | null;
  last_sync_error: string | null;
  automatic_sync_enabled: boolean;
  automatic_sync_interval_hours: number | null;
  automatic_sync_next_at: string | null;
  automatic_sync_note: string;
  comments_scope_granted: boolean;
  comments_reconnect_required: boolean;
};

export type YoutubeVideoRow = {
  youtube_video_id: string;
  title: string;
  published_at: string;
  thumbnail_url: string | null;
  views: number;
  likes: number;
  comments: number;
  engagement_rate: number;
};

export type YoutubeTopVideoRow = YoutubeVideoRow & { score: number };

/** Deterministic structured metadata shared by /videos and /videos/{id} (Sprint 5/6). */
export type YoutubeStructuredMetadata = {
  views_per_day: number;
  engagement_rate: number;
  trend: string;
  performance_score: number;
  performance_label: string;
  engagement_category: string;
  growth_category: string;
  topic_keywords: string[];
  velocity: number | null;
  acceleration: number | null;
  views_gained_24h: number | null;
  views_gained_7d: number | null;
  views_gained_30d: number | null;
  peak_growth_date: string | null;
  peak_growth_views: number | null;
  largest_slowdown_date: string | null;
  largest_slowdown_views: number | null;
  snapshot_count: number;
};

/** Shape returned by the GET /videos endpoint. */
export type YoutubeChannelVideo = YoutubeStructuredMetadata & {
  youtube_video_id: string;
  title: string;
  published_at: string;
  thumbnail_url: string | null;
  duration_seconds: number | null;
  is_short_candidate: boolean;
  views: number;
  likes: number;
  comments: number;
};

export type YoutubeScatterPoint = {
  youtube_video_id: string;
  title: string;
  views: number;
  likes: number;
};

export type YoutubeTimeseriesPoint = { date: string; value: number };

export type YoutubeUploadBucket = { bucket: string; count: number };

export type YoutubeVideoDetail = Omit<YoutubeStructuredMetadata, "views_per_day"> & {
  youtube_video_id: string;
  title: string;
  description: string;
  published_at: string;
  thumbnail_url: string | null;
  duration_seconds: number | null;
  is_short_candidate: boolean;
  views: number;
  likes: number;
  comments: number;
  engagement_rate: number;
  views_per_day: number;
  like_ratio: number;
  comment_ratio: number;
};

export type YoutubeVideoHistoryPoint = {
  captured_at: string;
  views: number;
  likes: number;
  comments: number;
};

export type YoutubeVideoHistoryBucket = {
  label: string;
  period_start: string;
  period_end: string;
  views: number;
  likes: number;
  comments: number;
};

export type YoutubeVideoHistory = {
  points: YoutubeVideoHistoryPoint[];
  granularity: "daily" | "weekly" | "monthly";
  buckets: YoutubeVideoHistoryBucket[];
  insufficient: boolean;
};

export type YoutubeChannelHistoryBucket = {
  label: string;
  period_start: string;
  period_end: string;
  subscriber_count: number;
  view_count: number;
  video_count: number;
};

export type YoutubeChannelHistory = {
  granularity: "daily" | "weekly" | "monthly";
  buckets: YoutubeChannelHistoryBucket[];
  insufficient: boolean;
};

export type YoutubeDataQualityReport = {
  videos_checked: number;
  snapshots_checked: number;
  exact_duplicate_snapshots_found: number;
  exact_duplicate_snapshots_repaired: number;
  impossible_timestamps: Record<string, unknown>[];
  non_monotonic_view_drops: Record<string, unknown>[];
  naive_timestamps_found: number;
  is_clean: boolean;
};

// --- Community Inbox (Release 0.7.0) ----------------------------------------

export type ReplyRead = {
  platform_comment_id: string;
  author_channel_id: string | null;
  author_display_name: string;
  author_avatar_url: string | null;
  text_original: string;
  like_count: number;
  published_at: string;
  updated_at: string;
  is_own_reply: boolean;
};

export type CommentThreadRead = {
  platform_thread_id: string;
  youtube_video_id: string;
  video_title: string;
  video_thumbnail_url: string | null;
  top_level_comment_id: string;
  author_channel_id: string | null;
  author_display_name: string;
  author_avatar_url: string | null;
  text_original: string;
  like_count: number;
  published_at: string;
  updated_at: string;
  total_reply_count: number;
  can_reply: boolean;
  is_answered: boolean;
  is_likely_question: boolean;
  priority_score: number;
  replies: ReplyRead[];
};

export type CommentInboxSummary = {
  total_visible: number;
  unanswered_count: number;
  questions_count: number;
  recent_count: number;
  with_replies_count: number;
};

export type CommentInboxRead = {
  summary: CommentInboxSummary;
  threads: CommentThreadRead[];
};

export type CommentSyncStatus = {
  last_synced_at: string | null;
  last_sync_status: string | null;
  last_sync_duration_seconds: number | null;
  last_sync_threads_discovered: number | null;
  last_sync_comments_imported: number | null;
  last_sync_replies_imported: number | null;
  last_sync_videos_failed: number | null;
  last_sync_error: string | null;
  automatic_sync_enabled: boolean;
  automatic_sync_next_at: string | null;
  comments_scope_granted: boolean;
};

export type QuickReplyTemplate = { id: number; text: string; position: number };

export type CommentQuickFilter = "all" | "unanswered" | "answered" | "questions" | "recent" | "with_replies";
export type CommentSort = "newest" | "oldest" | "most_liked" | "priority";

export type SupportingVideo = { youtube_video_id: string; title: string; thumbnail_url: string | null };

export type Confidence = "low" | "medium" | "high";

export type RecommendationData = {
  id: string;
  category: string;
  headline: string;
  explanation: string;
  confidence: Confidence;
  supporting_metrics: Record<string, number>;
  supporting_videos: SupportingVideo[];
};

export type DailyBrief = {
  views_gained_24h: number | null;
  subscribers_gained_24h: number | null;
  best_growing_video: SupportingVideo | null;
  best_growing_video_gain: number | null;
  biggest_slowdown_video: SupportingVideo | null;
  biggest_slowdown_delta: number | null;
  attention_video_count: number;
  days_since_last_upload: number | null;
  no_upload_warning: string | null;
};

export type TopicSummary = {
  keyword: string;
  video_count: number;
  median_views: number;
  median_views_per_day: number;
  median_engagement: number;
  best_video: SupportingVideo | null;
  worst_video: SupportingVideo | null;
  trend: string;
};

export type PublishingInsight = {
  best_weekday: string | null;
  best_weekday_median_vpd: number | null;
  best_hour: number | null;
  best_hour_median_vpd: number | null;
  best_cadence_label: string | null;
  best_cadence_median_vpd: number | null;
  best_streak_start: string | null;
  best_streak_end: string | null;
  best_streak_video_count: number | null;
  best_streak_avg_vpd: number | null;
  worst_streak_start: string | null;
  worst_streak_end: string | null;
  worst_streak_video_count: number | null;
  worst_streak_avg_vpd: number | null;
  insufficient_data_notes: string[];
};

export type IntelligenceReport = {
  daily_brief: DailyBrief;
  winning_videos: RecommendationData[];
  attention_videos: RecommendationData[];
  too_new_count: number;
  topics: TopicSummary[];
  publishing: PublishingInsight;
  follow_up_opportunities: RecommendationData[];
  title_patterns: RecommendationData[];
  content_recommendations: RecommendationData[];
};

async function getJson<T>(url: string, fallback: T): Promise<T> {
  try {
    const response = await fetch(url, { cache: "no-store" });
    return response.ok ? ((await response.json()) as T) : fallback;
  } catch {
    return fallback;
  }
}

export function createYoutubeApi(baseUrl: string) {
  const prefix = `${baseUrl}/api/integrations/youtube`;
  return {
    getSummary: () => getJson<YoutubeSummary | null>(`${prefix}/analytics/summary`, null),
    getTopVideos: (metric: "views" | "engagement", limit = 10) =>
      getJson<YoutubeTopVideoRow[]>(`${prefix}/analytics/top?metric=${metric}&limit=${limit}`, []),
    getRecentVideos: (limit = 10) => getJson<YoutubeVideoRow[]>(`${prefix}/analytics/recent?limit=${limit}`, []),
    getScatter: () => getJson<YoutubeScatterPoint[]>(`${prefix}/analytics/scatter`, []),
    getTimeseries: (metric: "views" | "likes" | "comments") =>
      getJson<YoutubeTimeseriesPoint[]>(`${prefix}/analytics/timeseries?metric=${metric}`, []),
    getUploadFrequency: (interval: "week" | "month" = "month") =>
      getJson<YoutubeUploadBucket[]>(`${prefix}/analytics/upload-frequency?interval=${interval}`, []),
    getVideos: () => getJson<YoutubeChannelVideo[]>(`${prefix}/videos`, []),
    getVideoDetail: (id: string) => getJson<YoutubeVideoDetail | null>(`${prefix}/videos/${id}`, null),
    getVideoHistory: (id: string) =>
      getJson<YoutubeVideoHistory>(`${prefix}/videos/${id}/history`, { points: [], granularity: "daily", buckets: [], insufficient: true }),
    getChannelHistory: () =>
      getJson<YoutubeChannelHistory | null>(`${prefix}/channel/history`, null),
    getDataQuality: () => getJson<YoutubeDataQualityReport | null>(`${prefix}/data-quality`, null),
    getIntelligence: () => getJson<IntelligenceReport | null>(`${prefix}/analytics/intelligence`, null),
    getStatus: () => getJson<YoutubeStatus | null>(`${prefix}/status`, null),
    getComments: (params: { quick?: CommentQuickFilter; video?: string; q?: string; sort?: CommentSort } = {}) => {
      const search = new URLSearchParams();
      if (params.quick && params.quick !== "all") search.set("quick", params.quick);
      if (params.video) search.set("video", params.video);
      if (params.q) search.set("q", params.q);
      if (params.sort) search.set("sort", params.sort);
      const qs = search.toString();
      return getJson<CommentInboxRead>(`${prefix}/comments${qs ? `?${qs}` : ""}`, {
        summary: { total_visible: 0, unanswered_count: 0, questions_count: 0, recent_count: 0, with_replies_count: 0 },
        threads: [],
      });
    },
    getCommentSyncStatus: () => getJson<CommentSyncStatus | null>(`${prefix}/comments/sync-status`, null),
    getQuickReplies: () => getJson<QuickReplyTemplate[]>(`${prefix}/quick-replies`, []),
  };
}
