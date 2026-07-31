import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PlatformSectionNav } from "./platform-section-nav";
import { PlatformStatusBar } from "./platform-status-bar";
import { RecommendationCard } from "./recommendation-card";
import { SynchronizationCenter } from "./synchronization-center";
import { platformPath } from "../lib/platform-api";

vi.mock("next/link", () => ({ default: ({ children, href, ...props }: { children: ReactNode; href: string }) => <a href={href} {...props}>{children}</a> }));

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("unified platform experience", () => {
  it("makes platform status tiles real navigation links", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ platforms: [
        { platform: "youtube", connected: true, last_synced_at: null, last_sync_status: "success" },
        { platform: "facebook", connected: true, last_synced_at: null, last_sync_status: "success" },
        { platform: "instagram", connected: true, last_synced_at: null, last_sync_status: "success" },
      ] }),
    }));
    render(<PlatformStatusBar />);
    expect((await screen.findByRole("link", { name: /YouTube/ })).getAttribute("href")).toBe("/youtube");
    expect(screen.getByRole("link", { name: /Facebook/ }).getAttribute("href")).toBe("/platforms/facebook");
    expect(screen.getByRole("link", { name: /Instagram/ }).getAttribute("href")).toBe("/platforms/instagram");
  });

  it("renders a large linked thumbnail with a platform marker", () => {
    render(<RecommendationCard platform="instagram" recommendation={{
      id: "r1",
      category: "winner",
      headline: "Najlepszy materiał",
      explanation: "Opis",
      confidence: "high",
      supporting_metrics: {},
      supporting_videos: [{ youtube_video_id: "v1", title: "Materiał", thumbnail_url: "https://example.test/thumb.jpg" }],
    }} />);
    expect(screen.getByRole("link", { name: /Instagram.*Materiał/s }).getAttribute("href")).toBe("/youtube/videos/v1");
    expect(screen.getByText("Otwórz materiał →")).toBeTruthy();
  });

  it("uses the same five sections and keeps YouTube on its full-depth routes", () => {
    render(<PlatformSectionNav platform="youtube" active="videos" />);
    for (const label of ["Dashboard", "Materiały", "Porównanie", "Co dalej?", "Komentarze"]) {
      expect(screen.getByRole("link", { name: label })).toBeTruthy();
    }
    expect(platformPath("youtube", "videos")).toBe("/youtube/videos");
    expect(platformPath("facebook", "videos")).toBe("/platforms/facebook/videos");
  });

  it("shows every platform and starts one aggregate synchronization", async () => {
    const overview = {
      platforms: [
        { platform: "youtube", connected: true, configured: true, display_name: "Kanał", last_synced_at: null, last_sync_status: "success", last_sync_error: null, scheduler_enabled: false, scheduler_interval_hours: null, next_scheduled_sync_at: null },
        { platform: "facebook", connected: false, configured: true, display_name: null, last_synced_at: null, last_sync_status: null, last_sync_error: null, scheduler_enabled: false, scheduler_interval_hours: null, next_scheduled_sync_at: null },
        { platform: "instagram", connected: false, configured: true, display_name: null, last_synced_at: null, last_sync_status: null, last_sync_error: null, scheduler_enabled: false, scheduler_interval_hours: null, next_scheduled_sync_at: null },
      ],
      history: [],
    };
    const syncResult = {
      status: "success",
      started_at: new Date().toISOString(),
      finished_at: new Date().toISOString(),
      results: [
        { platform: "youtube", status: "success", message: "OK", imported_items: 1, snapshots_created: 1, comments_imported: 0 },
        { platform: "facebook", status: "skipped", message: "Niepołączono", imported_items: 0, snapshots_created: 0, comments_imported: 0 },
        { platform: "instagram", status: "skipped", message: "Niepołączono", imported_items: 0, snapshots_created: 0, comments_imported: 0 },
      ],
    };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => overview })
      .mockResolvedValueOnce({ ok: true, json: async () => syncResult })
      .mockResolvedValueOnce({ ok: true, json: async () => overview });
    vi.stubGlobal("fetch", fetchMock);

    render(<SynchronizationCenter />);
    await screen.findByText("Kanał");
    expect(screen.getByText("TikTok")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Synchronizuj wszystko" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/sync-all"), { method: "POST" }));
    expect(await screen.findByText(/Wynik zbiorczy/)).toBeTruthy();
  });

  it("shows real synchronization progress while a request is running", async () => {
    const overview = {
      platforms: [
        { platform: "youtube", connected: true, configured: true, display_name: "Kanał", last_synced_at: null, last_sync_status: "running", last_sync_error: null, scheduler_enabled: false, scheduler_interval_hours: null, next_scheduled_sync_at: null },
        { platform: "facebook", connected: false, configured: true, display_name: null, last_synced_at: null, last_sync_status: null, last_sync_error: null, scheduler_enabled: false, scheduler_interval_hours: null, next_scheduled_sync_at: null },
        { platform: "instagram", connected: false, configured: true, display_name: null, last_synced_at: null, last_sync_status: null, last_sync_error: null, scheduler_enabled: false, scheduler_interval_hours: null, next_scheduled_sync_at: null },
      ],
      history: [{ id: 1, platform: "youtube", kind: "content", status: "running", started_at: new Date().toISOString(), finished_at: null, imported_items: 1, items_discovered: 10, items_processed: 4, snapshots_created: 4, comments_imported: 0, error_message: null }],
    };
    let finishSync!: (value: unknown) => void;
    const pendingSync = new Promise((resolve) => { finishSync = resolve; });
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => overview })
      .mockReturnValueOnce(pendingSync)
      .mockResolvedValue({ ok: true, json: async () => ({ ...overview, history: [] }) });
    vi.stubGlobal("fetch", fetchMock);

    render(<SynchronizationCenter />);
    await screen.findByText("Kanał");
    fireEvent.click(screen.getByRole("button", { name: "Synchronizuj wszystko" }));

    const progress = await screen.findByRole("progressbar", { name: "Postęp synchronizacji" });
    expect(progress.getAttribute("aria-valuenow")).toBe("40");
    expect(screen.getByText(/4 z 10/)).toBeTruthy();

    await act(async () => {
      finishSync({ ok: true, json: async () => ({ status: "success", results: [] }) });
    });
  });
});
