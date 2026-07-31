import { PLATFORM_LABELS, type PlatformKey } from "../lib/platform-api";

const PLATFORM_ICONS: Record<PlatformKey, string> = { youtube: "▶", facebook: "f", instagram: "◎" };

export function PlatformBadge({ platform }: { platform: PlatformKey }) {
  return (
    <span className={`contentPlatformBadge ${platform}`} aria-label={`Platforma: ${PLATFORM_LABELS[platform]}`}>
      <span className="contentPlatformIcon" aria-hidden="true">{PLATFORM_ICONS[platform]}</span>
      {PLATFORM_LABELS[platform]}
    </span>
  );
}
