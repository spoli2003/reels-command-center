import { isPerformanceLabelKey, PERFORMANCE_LABELS } from "../lib/youtube-metrics";

/** Emoji + text badge — label meaning is never conveyed by color alone. */
export function PerformanceLabelBadge({ label }: { label: string | undefined | null }) {
  if (!isPerformanceLabelKey(label)) return null;
  const { emoji, text, tone } = PERFORMANCE_LABELS[label];
  return (
    <span className={`performanceBadge ${tone}`} title={`Etykieta wydajności: ${text}`}>
      {emoji} {text}
    </span>
  );
}
