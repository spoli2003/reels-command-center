import Link from "next/link";

import { PLATFORM_LABELS, type PlatformKeyOrAll } from "../lib/platform-api";

const PLATFORMS: PlatformKeyOrAll[] = ["all", "youtube", "facebook", "instagram"];
const PLATFORM_ICONS: Record<PlatformKeyOrAll, string> = { all: "◆", youtube: "▶", facebook: "f", instagram: "◎" };

/**
 * Segmented control for switching the active platform lens (Part 7) while
 * staying on the same section — clicking "Facebook" while on Compare goes to
 * the Facebook Compare page, not back to a Dashboard. `sectionPath` builds
 * that per-platform URL; `connected` marks which real platforms have no
 * account yet so the control can show that at a glance.
 */
export function PlatformSwitcher({
  active,
  sectionPath,
  connected,
}: {
  active: PlatformKeyOrAll;
  sectionPath: (platform: PlatformKeyOrAll) => string;
  connected: Partial<Record<PlatformKeyOrAll, boolean>>;
}) {
  return (
    <div className="platformSwitcher" role="group" aria-label="Wybór platformy">
      {PLATFORMS.map((platform) => {
        const isDisconnected = platform !== "all" && connected[platform] === false;
        return (
          <Link
            key={platform}
            href={sectionPath(platform)}
            className={`platformSwitcherButton${active === platform ? " active" : ""}${isDisconnected ? " disconnected" : ""}`}
            title={isDisconnected ? `${PLATFORM_LABELS[platform]} nie jest jeszcze połączony` : undefined}
          >
            <span className="platformSwitcherIcon" aria-hidden="true">
              {PLATFORM_ICONS[platform]}
            </span>
            {PLATFORM_LABELS[platform]}
            {isDisconnected ? <span className="platformSwitcherDot" aria-hidden="true" /> : null}
          </Link>
        );
      })}
      <span className="platformSwitcherButton disconnected" title="Integracja TikTok jest planowana">
        <span className="platformSwitcherIcon" aria-hidden="true">♪</span>
        TikTok
        <span className="platformSwitcherDot" aria-hidden="true" />
      </span>
    </div>
  );
}
