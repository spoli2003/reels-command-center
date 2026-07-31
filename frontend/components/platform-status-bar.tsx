"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { PLATFORM_LABELS, type PlatformKey } from "../lib/platform-api";
import type { SynchronizationOverview } from "../lib/synchronization-api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const ICONS: Record<PlatformKey, string> = { youtube: "▶", facebook: "f", instagram: "◎" };
const ROUTES: Record<PlatformKey, string> = { youtube: "/youtube", facebook: "/platforms/facebook", instagram: "/platforms/instagram" };

function relativeSync(value: string | null) {
  if (!value) return "Jeszcze nie synchronizowano";
  const minutes = Math.max(0, Math.round((Date.now() - new Date(value).getTime()) / 60_000));
  if (minutes < 1) return "Przed chwilą";
  if (minutes < 60) return `${minutes} min temu`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} godz. temu`;
  return new Date(value).toLocaleDateString("pl-PL");
}

export function PlatformStatusBar({ compact = false }: { compact?: boolean }) {
  const [overview, setOverview] = useState<SynchronizationOverview | null>(null);

  useEffect(() => {
    let active = true;
    fetch(`${API_URL}/api/synchronization`, { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : null))
      .then((value) => {
        if (active) setOverview(value);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  return (
    <section className={`platformStatusBar${compact ? " compact" : ""}`} aria-label="Status platform">
      {(overview?.platforms ?? []).map((item) => (
        <Link key={item.platform} href={ROUTES[item.platform]} className={`platformStatusItem ${item.connected ? "connected" : "disconnected"}`}>
          <span className={`platformStatusIcon ${item.platform}`} aria-hidden="true">
            {ICONS[item.platform]}
          </span>
          <span>
            <strong>{PLATFORM_LABELS[item.platform]}</strong>
            <small>{item.connected ? relativeSync(item.last_synced_at) : "Niepołączono"}</small>
          </span>
          <i className={`platformStatusDot ${item.last_sync_status ?? "idle"}`} aria-label={item.last_sync_status ?? "brak synchronizacji"} />
        </Link>
      ))}
      <Link href="/synchronization" className="platformStatusItem planned" title="TikTok będzie dostępny w przyszłej wersji">
        <span className="platformStatusIcon tiktok" aria-hidden="true">♪</span>
        <span><strong>TikTok</strong><small>Wkrótce</small></span>
      </Link>
      <Link className="platformStatusAction" href="/synchronization">Synchronizacja →</Link>
    </section>
  );
}
