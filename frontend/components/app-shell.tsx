import Link from "next/link";
import type { ReactNode } from "react";

const NAV_ITEMS: { href: string; label: string; disabled?: boolean }[] = [
  { href: "/", label: "Dashboard" },
  { href: "/videos", label: "Filmy" },
  { href: "/youtube", label: "Analytics" },
  { href: "#", label: "AI", disabled: true },
  { href: "#", label: "Business", disabled: true },
  { href: "#", label: "Integracje", disabled: true },
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
              <Link key={item.label} href={item.href} className={item.href === active ? "active" : undefined}>
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
