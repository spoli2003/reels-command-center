import type { PlatformCommentInbox, PlatformCommentThread, PlatformKey, PlatformSummary, PlatformVideo } from "./platform-api";
import type { CommentInboxRead, CommentThreadRead } from "./youtube-api";

export type PlatformMetricTotals = {
  materials: number;
  views: number;
  interactions: number;
  comments: number;
  audience: number | null;
  viewsAvailable: boolean;
};

export type DashboardCommentThread = {
  platform: PlatformKey;
  platform_thread_id: string;
  external_id: string;
  video_title: string;
  author_display_name: string;
  text_original: string;
  conversation_state: string;
  last_message_at: string;
  is_likely_question: boolean;
  href: string;
};

export type DashboardCommentOverview = {
  summary: {
    awaiting_reply_count: number;
    new_count: number;
    waiting_count: number;
    resolved_count: number;
    recent_count: number;
  };
  threads: DashboardCommentThread[];
};

const PLATFORM_KEYS: PlatformKey[] = ["youtube", "facebook", "instagram"];

export function aggregatePlatformMetrics(videos: PlatformVideo[], summaries: PlatformSummary[]) {
  const byPlatform = Object.fromEntries(
    PLATFORM_KEYS.map((platform) => [platform, { materials: 0, views: 0, interactions: 0, comments: 0, audience: null, viewsAvailable: true }]),
  ) as Record<PlatformKey, PlatformMetricTotals>;

  for (const video of videos) {
    const total = byPlatform[video.platform];
    total.materials += 1;
    total.views += video.views;
    total.comments += video.comments;
    total.interactions += video.likes + video.comments + video.shares + video.saves;
  }
  for (const summary of summaries) {
    byPlatform[summary.platform].audience = summary.audience_count;
    byPlatform[summary.platform].viewsAvailable = summary.views_available;
  }

  const audienceValues = PLATFORM_KEYS.map((platform) => byPlatform[platform].audience).filter((value): value is number => value !== null);
  const total: PlatformMetricTotals = {
    materials: PLATFORM_KEYS.reduce((sum, platform) => sum + byPlatform[platform].materials, 0),
    views: PLATFORM_KEYS.reduce((sum, platform) => sum + byPlatform[platform].views, 0),
    interactions: PLATFORM_KEYS.reduce((sum, platform) => sum + byPlatform[platform].interactions, 0),
    comments: PLATFORM_KEYS.reduce((sum, platform) => sum + byPlatform[platform].comments, 0),
    audience: audienceValues.length ? audienceValues.reduce((sum, value) => sum + value, 0) : null,
    viewsAvailable: PLATFORM_KEYS.every((platform) => byPlatform[platform].viewsAvailable),
  };
  return { total, byPlatform };
}

function youtubeThread(thread: CommentThreadRead): DashboardCommentThread {
  return {
    platform: "youtube",
    platform_thread_id: thread.platform_thread_id,
    external_id: thread.youtube_video_id,
    video_title: thread.video_title,
    author_display_name: thread.author_display_name,
    text_original: thread.text_original,
    conversation_state: thread.conversation_state,
    last_message_at: thread.last_message_at,
    is_likely_question: thread.is_likely_question,
    href: `/youtube/videos/${thread.youtube_video_id}`,
  };
}

function metaThread(platform: "facebook" | "instagram", thread: PlatformCommentThread): DashboardCommentThread {
  return {
    platform,
    platform_thread_id: thread.platform_thread_id,
    external_id: thread.external_id,
    video_title: thread.video_title,
    author_display_name: thread.author_display_name,
    text_original: thread.text_original,
    conversation_state: thread.conversation_state,
    last_message_at: thread.last_message_at,
    is_likely_question: thread.is_likely_question,
    href: `/platforms/${platform}/videos/${thread.external_id}`,
  };
}

export function aggregateCommentInboxes(
  youtube: CommentInboxRead,
  facebook: PlatformCommentInbox,
  instagram: PlatformCommentInbox,
): DashboardCommentOverview {
  const summaries = [youtube.summary, facebook.summary, instagram.summary];
  return {
    summary: {
      awaiting_reply_count: summaries.reduce((sum, item) => sum + item.awaiting_reply_count, 0),
      new_count: summaries.reduce((sum, item) => sum + item.new_count, 0),
      waiting_count: summaries.reduce((sum, item) => sum + item.waiting_count, 0),
      resolved_count: summaries.reduce((sum, item) => sum + item.resolved_count, 0),
      recent_count: summaries.reduce((sum, item) => sum + item.recent_count, 0),
    },
    threads: [
      ...youtube.threads.map(youtubeThread),
      ...facebook.threads.map((thread) => metaThread("facebook", thread)),
      ...instagram.threads.map((thread) => metaThread("instagram", thread)),
    ].sort((left, right) => +new Date(right.last_message_at) - +new Date(left.last_message_at)),
  };
}
