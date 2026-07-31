import Link from "next/link";
import type { ReactNode } from "react";

const NAV_ITEMS: { href: string; label: string; disabled?: boolean; activePrefix?: string }[] = [
  { href: "/", label: "Dashboard" },
  { href: "/videos", label: "Filmy" },
  { href: "/youtube", label: "Analytics" },
  { href: "#", label: "AI", disabled: true },
  { href: "#", label: "Business", disabled: true },
  { href: "/platforms/all", label: "Platformy", activePrefix: "/platforms" },
  { href: "/synchronization", label: "Synchronizacja" },
  { href: "/faq/punktacja", label: "FAQ punktacji", activePrefix: "/faq" },
];

export function AppShell({ active, children }: { active: string; children: ReactNode }) {
  return (
    <div className="appShell">
      <aside className="sidebar">
        <Link className="brand" href="/">
          <span>359°</span>
          <strong>RCC</strong>
        </Link>
        <nav>
          {NAV_ITEMS.map((item) =>
            item.disabled ? (
              <a key={item.label} href={item.href}>
                {item.label}
              </a>
            ) : (
              <Link
                key={item.label}
                href={item.href}
                className={item.href === active || (item.activePrefix && active.startsWith(item.activePrefix)) ? "active" : undefined}
              >
                {item.label}
              </Link>
            ),
          )}
        </nav>
        <div className="sidebarFooter">
          <span className="statusDot" />
          System lokalny działa
        </div>
      </aside>
      <main className="workspace">{children}</main>
    </div>
  );
}
