/**
 * Validated against RCC's dark panel surface (#0c1320) with
 * scripts/validate_palette.js from the dataviz skill — all checks pass
 * (worst adjacent CVD ΔE 8.4, worst normal-vision ΔE 19.3, all >=3:1 contrast).
 */
export const CATEGORICAL_PALETTE = [
  "#3987e5", // blue
  "#d95926", // orange
  "#199e70", // aqua
  "#c98500", // yellow
  "#d55181", // magenta
  "#9085e9", // violet
  "#e66767", // red
];

export const BRAND_ACCENT = "#5cf0ac";

export const CHART_TOKENS = {
  grid: "#202a3d",
  axis: "#5b6980",
  tooltipBg: "#0c1320",
  tooltipBorder: "#29354a",
  textPrimary: "#f7f8fb",
  textSecondary: "#96a3b7",
};

export function seriesColor(index: number): string {
  return CATEGORICAL_PALETTE[index % CATEGORICAL_PALETTE.length];
}

export function compactNumber(value: number): string {
  return new Intl.NumberFormat("pl-PL", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}
