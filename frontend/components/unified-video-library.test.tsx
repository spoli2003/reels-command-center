import { cleanup, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { UnifiedVideoLibrary } from "./unified-video-library";
import type { PlatformSummary, PlatformVideo } from "../lib/platform-api";

vi.mock("next/link", () => ({ default: ({ children, href, ...props }: { children: ReactNode; href: string }) => <a href={href} {...props}>{children}</a> }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/videos",
  useSearchParams: () => new URLSearchParams(),
}));

afterEach(cleanup);

const video = (platform: PlatformVideo["platform"], id: string, views: number): PlatformVideo => ({
  external_id: id,
  platform,
  title: `${platform} film`,
  description: "",
  url: null,
  published_at: "2026-07-30T10:00:00Z",
  thumbnail_url: `https://example.test/${id}.jpg`,
  duration_seconds: 30,
  views,
  likes: 10,
  comments: 2,
  shares: 3,
  saves: 0,
  reach: null,
  impressions: null,
  followers_gained: null,
  engagement_rate: 1.2,
});

describe("unified video library", () => {
  it("renders all platforms, platform-aware links and honest unavailable Instagram views", () => {
    const videos = [video("youtube", "yt-1", 100), video("facebook", "fb-1", 200), video("instagram", "ig-1", 0)];
    const platforms: PlatformSummary[] = [
      { platform: "youtube", connected: true, display_name: "YT", audience_count: 1, views_available: true },
      { platform: "facebook", connected: true, display_name: "FB", audience_count: 2, views_available: true },
      { platform: "instagram", connected: true, display_name: "IG", audience_count: 3, views_available: false },
    ];

    render(<UnifiedVideoLibrary initialVideos={videos} platforms={platforms} />);

    expect(screen.getByLabelText("Platforma: YouTube")).toBeTruthy();
    expect(screen.getByLabelText("Platforma: Facebook")).toBeTruthy();
    expect(screen.getByLabelText("Platforma: Instagram")).toBeTruthy();
    expect(screen.getByTitle("youtube film").getAttribute("href")).toContain("/youtube/videos/yt-1");
    expect(screen.getByTitle("facebook film").getAttribute("href")).toContain("/platforms/facebook/videos/fb-1");
    expect(screen.getByTitle("instagram film").getAttribute("href")).toContain("/platforms/instagram/videos/ig-1");
    expect(screen.getAllByText("Brak danych").length).toBeGreaterThan(0);
    expect(screen.getByText("Instagram bez Insights pominięty")).toBeTruthy();
  });
});
