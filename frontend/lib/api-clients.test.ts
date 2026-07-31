import { afterEach, describe, expect, it, vi } from "vitest";

import { createPlatformApi } from "./platform-api";
import { createYoutubeApi } from "./youtube-api";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function responseWith(value: unknown) {
  return { ok: true, json: async () => value };
}

describe("audience gain API normalization", () => {
  it("normalizes a missing platform followers_gained field to null", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(responseWith([{
      external_id: "fb-1",
      platform: "facebook",
      title: "Film",
      description: "",
      url: null,
      published_at: null,
      thumbnail_url: null,
      duration_seconds: null,
      views: 10,
      likes: 1,
      comments: 1,
      shares: 0,
      saves: 0,
      reach: null,
      impressions: null,
      engagement_rate: 20,
    }])));

    const videos = await createPlatformApi("http://api.test", "facebook").getVideos();
    expect(videos[0].followers_gained).toBeNull();
  });

  it("normalizes a missing legacy YouTube followers_gained field to null", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(responseWith([{
      youtube_video_id: "yt-1",
      title: "Film",
      published_at: "2026-07-31T10:00:00Z",
      thumbnail_url: null,
      duration_seconds: 30,
      is_short_candidate: true,
      views: 10,
      likes: 1,
      comments: 1,
      views_per_day: 10,
      engagement_rate: 20,
      trend: "stable",
      performance_score: 50,
      performance_label: "average",
      engagement_category: "average",
      growth_category: "average",
      topic_keywords: [],
      velocity: null,
      acceleration: null,
      views_gained_24h: null,
      views_gained_7d: null,
      views_gained_30d: null,
      peak_growth_date: null,
      peak_growth_views: null,
      largest_slowdown_date: null,
      largest_slowdown_views: null,
      snapshot_count: 1,
    }])));

    const videos = await createYoutubeApi("http://api.test").getVideos();
    expect(videos[0].followers_gained).toBeNull();
  });

  it("does not hide an invalid present metric", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(responseWith([{
      external_id: "fb-1",
      platform: "facebook",
      title: "Film",
      description: "",
      url: null,
      published_at: null,
      thumbnail_url: null,
      duration_seconds: null,
      views: 10,
      likes: 1,
      comments: 1,
      shares: 0,
      saves: 0,
      reach: null,
      impressions: null,
      followers_gained: "unknown",
      engagement_rate: 20,
    }])));

    await expect(createPlatformApi("http://api.test", "facebook").getVideos()).rejects.toThrow("followers_gained");
  });
});
