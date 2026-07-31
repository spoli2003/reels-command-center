import Link from "next/link";

import { platformPath, type PlatformKeyOrAll, type PlatformSection } from "../lib/platform-api";

const SECTIONS: { key: PlatformSection; label: string }[] = [
  { key: "", label: "Dashboard" },
  { key: "videos", label: "Materiały" },
  { key: "compare", label: "Porównanie" },
  { key: "intelligence", label: "Co dalej?" },
  { key: "community", label: "Komentarze" },
];

/** Same visual pattern as PlatformSubNav, but platform-aware: Compare/
 * Intelligence/Community are hidden under "Wszystkie" (Part 7) since those
 * surfaces need one specific platform's own account. */
export function PlatformSectionNav({ platform, active }: { platform: PlatformKeyOrAll; active: PlatformSection }) {
  const visibleSections = platform === "all" ? SECTIONS.filter((section) => section.key === "" || section.key === "videos") : SECTIONS;
  return (
    <nav className="platformSubNav">
      {visibleSections.map((section) => (
        <Link
          key={section.key || "dashboard"}
          href={platformPath(platform, section.key)}
          className={section.key === active ? "platformSubNavLink active" : "platformSubNavLink"}
        >
          {section.label}
        </Link>
      ))}
    </nav>
  );
}
