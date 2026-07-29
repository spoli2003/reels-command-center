import type { Confidence } from "../lib/youtube-api";

const LABELS: Record<Confidence, string> = {
  low: "Niska pewność",
  medium: "Średnia pewność",
  high: "Wysoka pewność",
};

export function ConfidenceBadge({ confidence }: { confidence: Confidence }) {
  return <span className={`confidenceBadge ${confidence}`}>{LABELS[confidence]}</span>;
}
