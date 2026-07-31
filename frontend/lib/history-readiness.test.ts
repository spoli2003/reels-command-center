import { describe, expect, it } from "vitest";

import { historyReadiness } from "./history-readiness";

describe("historyReadiness", () => {
  it("keeps short, misleading history in collection mode and reports real gains", () => {
    const result = historyReadiness({
      views: [
        { date: "2026-07-29", value: 25_000 },
        { date: "2026-07-31", value: 27_700 },
      ],
      likes: [
        { date: "2026-07-29", value: 220 },
        { date: "2026-07-31", value: 240 },
      ],
      comments: [
        { date: "2026-07-29", value: 12 },
        { date: "2026-07-31", value: 17 },
      ],
      audience: [
        { period_start: "2026-07-29", subscriber_count: 235 },
        { period_start: "2026-07-30", subscriber_count: 237 },
      ],
    });

    expect(result).toMatchObject({
      ready: false,
      trackedDays: 3,
      remainingDays: 4,
      firstDate: "2026-07-29",
      viewsGain: 2_700,
      engagementGain: 25,
      subscribersGain: 2,
    });
  });

  it("enables trends after seven distinct tracking days", () => {
    const views = Array.from({ length: 7 }, (_, index) => ({
      date: `2026-07-${String(20 + index).padStart(2, "0")}`,
      value: 1_000 + index,
    }));

    expect(historyReadiness({ views, likes: [], comments: [], audience: [] }).ready).toBe(true);
  });
});
