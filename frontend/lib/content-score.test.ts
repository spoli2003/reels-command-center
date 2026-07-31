import { describe, expect, it } from "vitest";

import { computeExplainableScores, minMaxNormalize } from "./content-score";

describe("explainable content score", () => {
  it("preserves the 50/30/20 formula and exposes added/lost points", () => {
    const items = [
      { views: 0, views_per_day: 0, engagement_rate: 0 },
      { views: 40, views_per_day: 70, engagement_rate: 50 },
      { views: 100, views_per_day: 140, engagement_rate: 100 },
    ];

    const middle = computeExplainableScores(items)[1];
    expect(middle.performance_score).toBe(48);
    expect(middle.score_breakdown.components.map((item) => item.points_added)).toEqual([25, 15, 8]);
    expect(middle.score_breakdown.components.map((item) => item.points_lost)).toEqual([25, 15, 12]);
    expect(middle.score_breakdown.scope_size).toBe(3);
  });

  it("keeps the established no-variance normalization rule", () => {
    expect(minMaxNormalize(7, 7, 7)).toBe(100);
    expect(computeExplainableScores([{ views: 7, views_per_day: 7, engagement_rate: 7 }])[0].performance_score).toBe(100);
  });

  it("returns an empty set without inventing a score", () => {
    expect(computeExplainableScores([])).toEqual([]);
  });
});
