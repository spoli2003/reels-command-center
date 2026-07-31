export type ScoreMetricKey = "views_per_day" | "engagement" | "views";

export type ScoreableContent = { views: number; views_per_day: number; engagement_rate: number };

export type ScoreComponentBreakdown = {
  key: ScoreMetricKey;
  label: string;
  weight: number;
  raw_value: number;
  range_min: number;
  range_max: number;
  normalized: number;
  points_added: number;
  points_lost: number;
};

/** Legacy numeric fields remain because existing one-sentence explanations use them. */
export type ScoreBreakdown = {
  views: number;
  views_per_day: number;
  engagement: number;
  total: number;
  scope_size: number;
  components: ScoreComponentBreakdown[];
};

export const SCORE_COMPONENTS: ReadonlyArray<{ key: ScoreMetricKey; label: string; weight: number }> = [
  { key: "views_per_day", label: "Tempo wyświetleń", weight: 0.5 },
  { key: "engagement", label: "Zaangażowanie", weight: 0.3 },
  { key: "views", label: "Łączne wyświetlenia", weight: 0.2 },
];

function rounded(value: number): number {
  return Math.round(value * 100) / 100;
}

/** Same legacy rule: no variance means every item gets 100 for that component. */
export function minMaxNormalize(value: number, min: number, max: number): number {
  if (max === min) return 100;
  return ((value - min) / (max - min)) * 100;
}

function rawValue(item: ScoreableContent, key: ScoreMetricKey): number {
  if (key === "views_per_day") return item.views_per_day;
  if (key === "engagement") return item.engagement_rate;
  return item.views;
}

export type ExplainableScored<T extends ScoreableContent> = T & {
  performance_score: number;
  score_breakdown: ScoreBreakdown;
};

/** Preserves RCC's existing 50/30/20 score and adds its complete audit trail. */
export function computeExplainableScores<T extends ScoreableContent>(items: T[]): ExplainableScored<T>[] {
  if (items.length === 0) return [];
  const ranges = new Map<ScoreMetricKey, [number, number]>();
  for (const definition of SCORE_COMPONENTS) {
    const values = items.map((item) => rawValue(item, definition.key));
    ranges.set(definition.key, [Math.min(...values), Math.max(...values)]);
  }

  return items.map((item) => {
    const components = SCORE_COMPONENTS.map((definition): ScoreComponentBreakdown => {
      const value = rawValue(item, definition.key);
      const [min, max] = ranges.get(definition.key)!;
      const normalized = minMaxNormalize(value, min, max);
      const maximumPoints = definition.weight * 100;
      const pointsAdded = normalized * definition.weight;
      return {
        ...definition,
        raw_value: value,
        range_min: min,
        range_max: max,
        normalized: rounded(normalized),
        points_added: rounded(pointsAdded),
        points_lost: rounded(Math.max(0, maximumPoints - pointsAdded)),
      };
    });
    const total = rounded(components.reduce((sum, component) => sum + component.points_added, 0));
    const byKey = new Map(components.map((component) => [component.key, component.normalized]));
    return {
      ...item,
      performance_score: total,
      score_breakdown: {
        views: byKey.get("views") ?? 0,
        views_per_day: byKey.get("views_per_day") ?? 0,
        engagement: byKey.get("engagement") ?? 0,
        total,
        scope_size: items.length,
        components,
      },
    };
  });
}

export function emptyScoreBreakdown(): ScoreBreakdown {
  return {
    views: 0,
    views_per_day: 0,
    engagement: 0,
    total: 0,
    scope_size: 0,
    components: SCORE_COMPONENTS.map((component) => ({
      ...component,
      raw_value: 0,
      range_min: 0,
      range_max: 0,
      normalized: 0,
      points_added: 0,
      points_lost: component.weight * 100,
    })),
  };
}
