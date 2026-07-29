import Link from "next/link";

export type PlatformSubNavTab = { href: string; label: string };

/**
 * Generic per-platform tab navigation. Not YouTube-specific — any platform
 * section (Facebook, Instagram, TikTok) reuses this with its own tab list.
 */
export function PlatformSubNav({ tabs, active }: { tabs: PlatformSubNavTab[]; active: string }) {
  return (
    <nav className="platformSubNav">
      {tabs.map((tab) => (
        <Link key={tab.href} href={tab.href} className={tab.href === active ? "platformSubNavLink active" : "platformSubNavLink"}>
          {tab.label}
        </Link>
      ))}
    </nav>
  );
}
