import { normalizeOptionalNullableNumber } from "./api-normalization";

// Generic multi-platform API client — Release 0.8.0 (Parts 5-9). Mirrors
// lib/youtube-api.ts's shape (same fetch-with-fallback pattern) but talks to
// /api/platforms/{platform}/... which serves YouTube (bridged), Facebook, and
// Instagram identically. Field names are platform-neutral (external_id, not
// youtube_video_id) since the backend's Publication/MetricSnapshot tables are
// shared by all three.

export type PlatformKey = "youtube" | "facebook" | "instagram";
export type PlatformKeyOrAll = PlatformKey | "all";

export const PLATFORM_LABELS: Record<PlatformKeyOrAll, string> = {
  all: "Wszystkie",
  youtube: "YouTube",
  facebook: "Facebook",
  instagram: "Instagram",
};

export type PlatformSummary = {
  platform: PlatformKey;
  connected: boolean;
  display_name: string | null;
  /** Latest channel/Page/profile audience size. null means unavailable, never zero-by-default. */
  audience_count: number | null;
  views_available: boolean;
};

export type PlatformStatus = {
  platform: PlatformKey;
  connected: boolean;
  configured: boolean;
  display_name: string | null;
  video_count: number;
  last_synced_at: string | null;
  last_sync_status: string | null;
  last_sync_error: string | null;
  last_comments_synced_at: string | null;
  last_comments_sync_status: string | null;
  last_comments_sync_error: string | null;
  required_permissions: string[];
  granted_permissions: string[];
  missing_permissions: string[];
  optional_permissions: string[];
  missing_optional_permissions: string[];
  scheduler_enabled: boolean;
  next_scheduled_sync_at: string | null;
  message: string;
};

export type PlatformVideo = {
  external_id: string;
  platform: PlatformKey;
  title: string;
  description: string;
  url: string | null;
  published_at: string | null;
  thumbnail_url: string | null;
  duration_seconds: number | null;
  views: number;
  likes: number;
  comments: number;
  shares: number;
  saves: number;
  reach: number | null;
  impressions: number | null;
  followers_gained: number | null;
  engagement_rate: number;
};

type PlatformVideoWire = Omit<PlatformVideo, "followers_gained"> & { followers_gained?: unknown };

export function normalizePlatformVideo(video: PlatformVideoWire): PlatformVideo {
  const { followers_gained: rawFollowersGained, ...rest } = video;
  return {
    ...rest,
    followers_gained: normalizeOptionalNullableNumber(rawFollowersGained, "followers_gained"),
  };
}

export type PlatformVideoHistoryPoint = { captured_at: string; views: number; likes: number; comments: number };
export type PlatformVideoHistoryBucket = {
  label: string;
  period_start: string;
  period_end: string;
  views: number;
  likes: number;
  comments: number;
};
export type PlatformVideoHistory = {
  points: PlatformVideoHistoryPoint[];
  granularity: "daily" | "weekly" | "monthly";
  buckets: PlatformVideoHistoryBucket[];
  insufficient: boolean;
};

// --- Community Inbox (generic) ----------------------------------------------

export type ConversationState = "new" | "waiting" | "resolved" | "closed";

export type PlatformReply = {
  platform_comment_id: string;
  author_external_id: string | null;
  author_display_name: string;
  author_avatar_url: string | null;
  text_original: string;
  like_count: number;
  published_at: string;
  updated_at: string;
  is_own_reply: boolean;
};

export type PlatformCommentThread = {
  platform_thread_id: string;
  external_id: string;
  video_title: string;
  video_thumbnail_url: string | null;
  top_level_comment_id: string;
  author_external_id: string | null;
  author_display_name: string;
  author_avatar_url: string | null;
  text_original: string;
  like_count: number;
  published_at: string;
  updated_at: string;
  total_reply_count: number;
  can_reply: boolean;
  is_own_thread: boolean;
  conversation_state: ConversationState;
  last_message_at: string;
  is_likely_question: boolean;
  is_highly_liked: boolean;
  priority_score: number;
  replies: PlatformReply[];
};

export type PlatformCommentInboxSummary = {
  total_visible: number;
  own_threads_count: number;
  new_count: number;
  waiting_count: number;
  resolved_count: number;
  closed_count: number;
  awaiting_reply_count: number;
  questions_count: number;
  recent_count: number;
  with_replies_count: number;
};

export type PlatformCommentInbox = { summary: PlatformCommentInboxSummary; threads: PlatformCommentThread[] };

export type QuickReplyTemplate = { id: number; text: string; position: number };

export type CommentQuickFilter = "all" | "mine" | "new" | "waiting" | "resolved" | "closed" | "questions" | "recent" | "with_replies" | "highly_liked";
export type CommentSort = "newest" | "oldest" | "most_liked" | "most_replies" | "priority" | "recently_active";

// --- Creator Intelligence (generic — same shape the YouTube adapter produces) --

export type PlatformSupportingVideo = { external_id: string; title: string; thumbnail_url: string | null };
export type Confidence = "low" | "medium" | "high";

export type PlatformRecommendation = {
  id: string;
  category: string;
  headline: string;
  explanation: string;
  confidence: Confidence;
  supporting_metrics: Record<string, number>;
  supporting_videos: PlatformSupportingVideo[];
};

export type PlatformDailyBrief = {
  views_gained_24h: number | null;
  subscribers_gained_24h: number | null;
  best_growing_video: PlatformSupportingVideo | null;
  best_growing_video_gain: number | null;
  biggest_slowdown_video: PlatformSupportingVideo | null;
  biggest_slowdown_delta: number | null;
  attention_video_count: number;
  days_since_last_upload: number | null;
  no_upload_warning: string | null;
};

export type PlatformTopicSummary = {
  keyword: string;
  video_count: number;
  median_views: number;
  median_views_per_day: number;
  median_engagement: number;
  best_video: PlatformSupportingVideo | null;
  worst_video: PlatformSupportingVideo | null;
  trend: string;
};

export type PlatformPublishingInsight = {
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

export type PlatformIntelligenceReport = {
  daily_brief: PlatformDailyBrief;
  winning_videos: PlatformRecommendation[];
  attention_videos: PlatformRecommendation[];
  too_new_count: number;
  topics: PlatformTopicSummary[];
  publishing: PlatformPublishingInsight;
  follow_up_opportunities: PlatformRecommendation[];
  title_patterns: PlatformRecommendation[];
  content_recommendations: PlatformRecommendation[];
};

/**
 * Meta occasionally returns legacy captions containing an unpaired UTF-16
 * surrogate. React renders that value differently on the server and in the
 * browser, which causes a hydration mismatch for an otherwise valid row.
 * Normalize all API strings at the boundary so every platform uses the same,
 * well-formed text on both sides of hydration.
 */
export function toWellFormedText(value: string): string {
  let result = "";
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index);
    if (code >= 0xd800 && code <= 0xdbff) {
      const next = value.charCodeAt(index + 1);
      if (next >= 0xdc00 && next <= 0xdfff) {
        result += value[index] + value[index + 1];
        index += 1;
      } else {
        result += "\ufffd";
      }
    } else if (code >= 0xdc00 && code <= 0xdfff) {
      result += "\ufffd";
    } else {
      result += value[index];
    }
  }
  return result;
}

function normalizeJsonStrings<T>(value: T): T {
  if (typeof value === "string") return toWellFormedText(value) as T;
  if (Array.isArray(value)) return value.map((item) => normalizeJsonStrings(item)) as T;
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([key, item]) => [key, normalizeJsonStrings(item)]),
    ) as T;
  }
  return value;
}

async function getJson<T>(url: string, fallback: T): Promise<T> {
  try {
    const response = await fetch(url, { cache: "no-store" });
    return response.ok ? normalizeJsonStrings((await response.json()) as T) : fallback;
  } catch {
    return fallback;
  }
}

const EMPTY_INBOX: PlatformCommentInbox = {
  summary: {
    total_visible: 0,
    own_threads_count: 0,
    new_count: 0,
    waiting_count: 0,
    resolved_count: 0,
    closed_count: 0,
    awaiting_reply_count: 0,
    questions_count: 0,
    recent_count: 0,
    with_replies_count: 0,
  },
  threads: [],
};

export function createPlatformApi(baseUrl: string, platform: PlatformKeyOrAll) {
  const prefix = `${baseUrl}/api/platforms/${platform}`;
  return {
    getStatus: () => getJson<PlatformStatus | null>(`${prefix}/status`, null),
    getVideos: async () => (await getJson<PlatformVideoWire[]>(`${prefix}/videos`, [])).map(normalizePlatformVideo),
    getVideoDetail: async (externalId: string) => {
      const video = await getJson<PlatformVideoWire | null>(`${prefix}/videos/${externalId}`, null);
      return video ? normalizePlatformVideo(video) : null;
    },
    getVideoHistory: (externalId: string) =>
      getJson<PlatformVideoHistory>(`${prefix}/videos/${externalId}/history`, {
        points: [],
        granularity: "daily",
        buckets: [],
        insufficient: true,
      }),
    getIntelligence: () => getJson<PlatformIntelligenceReport | null>(`${prefix}/intelligence`, null),
    getComments: (params: { quick?: CommentQuickFilter; video?: string; author?: string; q?: string; sort?: CommentSort } = {}) => {
      const search = new URLSearchParams();
      if (params.quick && params.quick !== "all") search.set("quick", params.quick);
      if (params.video) search.set("video", params.video);
      if (params.author) search.set("author", params.author);
      if (params.q) search.set("q", params.q);
      if (params.sort) search.set("sort", params.sort);
      const qs = search.toString();
      return getJson<PlatformCommentInbox>(`${prefix}/comments${qs ? `?${qs}` : ""}`, EMPTY_INBOX);
    },
    getQuickReplies: () => getJson<QuickReplyTemplate[]>(`${prefix}/quick-replies`, []),
  };
}

export function createPlatformOverviewApi(baseUrl: string) {
  return { listPlatforms: () => getJson<PlatformSummary[]>(`${baseUrl}/api/platforms`, []) };
}

export type PlatformSection = "" | "videos" | "compare" | "intelligence" | "community";

/** Builds a /platforms/{platform}[/section] URL. Compare/Intelligence/Community
 * are scoped to one real platform's own account — "all" only ever resolves to
 * Dashboard or Videos (the two surfaces that make sense merged). */
export function platformPath(platform: PlatformKeyOrAll, section: PlatformSection = ""): string {
  const safeSection = platform === "all" && section !== "videos" ? "" : section;
  if (platform === "youtube") return `/youtube${safeSection ? `/${safeSection}` : ""}`;
  return `/platforms/${platform}${safeSection ? `/${safeSection}` : ""}`;
}
