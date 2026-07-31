import { describe, expect, it } from "vitest";

import { aggregateCommentInboxes, aggregatePlatformMetrics } from "./dashboard-aggregation";
import type { PlatformCommentInbox, PlatformSummary, PlatformVideo } from "./platform-api";
import type { CommentInboxRead } from "./youtube-api";

const emptySummary = {
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
};

describe("all-platform dashboard aggregation", () => {
  it("returns totals and a truthful per-platform breakdown", () => {
    const videos = [
      { platform: "youtube", views: 100, likes: 10, comments: 2, shares: 1, saves: 0 },
      { platform: "facebook", views: 200, likes: 20, comments: 3, shares: 2, saves: 1 },
      { platform: "instagram", views: 0, likes: 30, comments: 4, shares: 0, saves: 0 },
    ] as PlatformVideo[];
    const summaries = [
      { platform: "youtube", connected: true, display_name: "YT", audience_count: 1000, views_available: true },
      { platform: "facebook", connected: true, display_name: "FB", audience_count: 2000, views_available: true },
      { platform: "instagram", connected: true, display_name: "IG", audience_count: 3000, views_available: false },
    ] as PlatformSummary[];

    const result = aggregatePlatformMetrics(videos, summaries);
    expect(result.total.views).toBe(300);
    expect(result.total.audience).toBe(6000);
    expect(result.total.comments).toBe(9);
    expect(result.byPlatform.facebook.interactions).toBe(26);
    expect(result.byPlatform.instagram.viewsAvailable).toBe(false);
  });

  it("combines YouTube, Facebook and Instagram conversations", () => {
    const youtube = {
      summary: { ...emptySummary, awaiting_reply_count: 1, new_count: 1 },
      threads: [{
        platform_thread_id: "yt-thread",
        youtube_video_id: "yt-video",
        video_title: "YT",
        author_display_name: "A",
        text_original: "YT comment",
        conversation_state: "new",
        last_message_at: "2026-07-30T10:00:00Z",
        is_likely_question: true,
      }],
    } as CommentInboxRead;
    const facebook = {
      summary: { ...emptySummary, awaiting_reply_count: 2, waiting_count: 2 },
      threads: [{
        platform_thread_id: "fb-thread",
        external_id: "fb-video",
        video_title: "FB",
        author_display_name: "B",
        text_original: "FB comment",
        conversation_state: "waiting",
        last_message_at: "2026-07-31T10:00:00Z",
        is_likely_question: false,
      }],
    } as PlatformCommentInbox;
    const instagram = { summary: { ...emptySummary, resolved_count: 3, recent_count: 3 }, threads: [] } as PlatformCommentInbox;

    const result = aggregateCommentInboxes(youtube, facebook, instagram);
    expect(result.summary.awaiting_reply_count).toBe(3);
    expect(result.summary.resolved_count).toBe(3);
    expect(result.threads.map((thread) => thread.platform)).toEqual(["facebook", "youtube"]);
    expect(result.threads[0].href).toBe("/platforms/facebook/videos/fb-video");
  });
});
