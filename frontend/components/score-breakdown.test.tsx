import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { AudienceGain } from "./audience-gain";
import { PlatformBadge } from "./platform-badge";
import { ScoreBreakdownDetails } from "./score-breakdown";
import { computeExplainableScores } from "../lib/content-score";

vi.mock("next/link", () => ({ default: ({ children, href }: { children: ReactNode; href: string }) => <a href={href}>{children}</a> }));

describe("ranking explanation components", () => {
  it("shows the platform name and icon", () => {
    render(<PlatformBadge platform="instagram" />);
    expect(screen.getByText("Instagram")).toBeTruthy();
    expect(screen.getByText("◎")).toBeTruthy();
  });

  it("uses an honest fallback when per-item audience attribution is unavailable", () => {
    render(<AudienceGain platform="youtube" value={null} />);
    expect(screen.getByText("Pozyskani: brak danych")).toBeTruthy();
  });

  it("renders added and lost points plus a methodology link", () => {
    const breakdown = computeExplainableScores([
      { views: 0, views_per_day: 0, engagement_rate: 0 },
      { views: 50, views_per_day: 50, engagement_rate: 50 },
      { views: 100, views_per_day: 100, engagement_rate: 100 },
    ])[1].score_breakdown;
    render(<ScoreBreakdownDetails breakdown={breakdown} defaultOpen />);
    expect(screen.getByText("Dlaczego 50 pkt?")).toBeTruthy();
    expect(screen.getAllByText(/pkt dodane/)).toHaveLength(3);
    expect(screen.getAllByText(/pkt do maksimum/)).toHaveLength(3);
    expect(screen.getByRole("link", { name: /Jak działa punktacja/ }).getAttribute("href")).toBe("/faq/punktacja");
  });
});
