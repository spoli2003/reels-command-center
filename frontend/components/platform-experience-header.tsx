import Link from "next/link";

import { PlatformSectionNav } from "./platform-section-nav";
import { PlatformStatusBar } from "./platform-status-bar";
import { PlatformSwitcher } from "./platform-switcher";
import { platformPath, type PlatformKeyOrAll, type PlatformSection } from "../lib/platform-api";

export function PlatformExperienceHeader({
  platform,
  section,
  connected,
  title,
  description,
}: {
  platform: PlatformKeyOrAll;
  section: PlatformSection;
  connected: Partial<Record<PlatformKeyOrAll, boolean>>;
  title: string;
  description: string;
}) {
  return (
    <>
      <header className="topbar">
        <div>
          <p className="eyebrow">PLATFORMY / {section ? section.toUpperCase() : "DASHBOARD"}</p>
          <h1>{title}</h1>
          <p className="muted">{description}</p>
        </div>
        <Link className="primaryButton" href="/synchronization">Synchronizuj →</Link>
      </header>
      <PlatformStatusBar compact />
      <PlatformSwitcher active={platform} sectionPath={(value) => platformPath(value, section)} connected={connected} />
      <PlatformSectionNav platform={platform} active={section} />
    </>
  );
}
