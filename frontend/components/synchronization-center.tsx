"use client";

import { useCallback, useEffect, useState } from "react";

import { PLATFORM_LABELS, type PlatformKey } from "../lib/platform-api";
import type { GlobalSyncResult, SynchronizationOverview } from "../lib/synchronization-api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const ICONS: Record<PlatformKey, string> = { youtube: "▶", facebook: "f", instagram: "◎" };
const STATUS_LABELS: Record<string, string> = {
  running: "Trwa",
  success: "Udana",
  partial: "Częściowa",
  failed: "Nieudana",
  skipped: "Pominięta",
};

function dateTime(value: string | null) {
  return value ? new Date(value).toLocaleString("pl-PL") : "Jeszcze nie wykonano";
}

export function SynchronizationCenter() {
  const [overview, setOverview] = useState<SynchronizationOverview | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [result, setResult] = useState<GlobalSyncResult | null>(null);
  const [notice, setNotice] = useState("");
  const activeRun = overview?.history.find((run) => run.status === "running");
  const progressPercent = activeRun?.items_discovered
    ? Math.min(100, Math.round((activeRun.items_processed / activeRun.items_discovered) * 100))
    : null;

  const load = useCallback(async () => {
    const response = await fetch(`${API_URL}/api/synchronization`, { cache: "no-store" });
    if (!response.ok) throw new Error("Nie udało się pobrać stanu synchronizacji.");
    setOverview(await response.json());
  }, []);

  useEffect(() => {
    load().catch((caught) => setError(caught instanceof Error ? caught.message : "Backend nie odpowiada."));
  }, [load]);

  useEffect(() => {
    if (busy === null) return;
    const timer = window.setInterval(() => load().catch(() => undefined), 1500);
    return () => window.clearInterval(timer);
  }, [busy, load]);

  async function syncAll() {
    setBusy("all");
    setError("");
    setNotice("");
    setResult(null);
    try {
      const response = await fetch(`${API_URL}/api/synchronization/sync-all`, { method: "POST" });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? "Synchronizacja nie powiodła się.");
      setResult(body);
      setNotice("Synchronizacja wszystkich połączonych platform została zakończona.");
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Synchronizacja nie powiodła się.");
    } finally {
      setBusy(null);
    }
  }

  async function syncOne(platform: PlatformKey) {
    setBusy(platform);
    setError("");
    setNotice("");
    try {
      const path = platform === "youtube" ? "/api/integrations/youtube/sync" : `/api/platforms/${platform}/sync`;
      const response = await fetch(`${API_URL}${path}`, { method: "POST" });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail ?? `Synchronizacja ${PLATFORM_LABELS[platform]} nie powiodła się.`);
      await load();
      setNotice(`Synchronizacja ${PLATFORM_LABELS[platform]} została zakończona.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Synchronizacja nie powiodła się.");
    } finally {
      setBusy(null);
    }
  }

  async function disconnect(platform: PlatformKey) {
    if (!confirm(`Odłączyć ${PLATFORM_LABELS[platform]}? Zsynchronizowane dane pozostaną w historii RCC.`)) return;
    const path = platform === "youtube" ? "/api/integrations/youtube/disconnect" : `/api/platforms/${platform}/disconnect`;
    await fetch(`${API_URL}${path}`, { method: "DELETE" });
    await load();
  }

  return (
    <>
      <section className="syncHero">
        <div>
          <p className="eyebrow">CENTRUM SYNCHRONIZACJI</p>
          <h2>Wszystkie źródła w jednym miejscu</h2>
          <p className="muted">Uruchamiaj synchronizację, sprawdzaj harmonogram i diagnozuj błędy bez zaśmiecania dashboardów.</p>
        </div>
        <button className="primaryButton" onClick={syncAll} disabled={busy !== null}>
          {busy === "all" ? "Synchronizuję wszystko…" : "Synchronizuj wszystko"}
        </button>
      </section>

      {busy !== null ? (
        <section className="syncProgress" aria-live="polite">
          <div className="syncProgressCopy">
            <strong>{busy === "all" ? "Synchronizacja wszystkich platform trwa" : `Synchronizacja ${PLATFORM_LABELS[busy as PlatformKey]} trwa`}</strong>
            <span>
              {activeRun
                ? `Teraz: ${PLATFORM_LABELS[activeRun.platform]} · ${activeRun.items_processed} z ${activeRun.items_discovered || "…"}`
                : "Przygotowanie i pobieranie danych…"}
            </span>
          </div>
          <div
            className={`syncProgressTrack${progressPercent === null ? " indeterminate" : ""}`}
            role="progressbar"
            aria-label="Postęp synchronizacji"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={progressPercent ?? undefined}
            aria-valuetext={progressPercent === null ? "Pobieranie listy materiałów" : `${progressPercent}%`}
          >
            <span style={progressPercent === null ? undefined : { width: `${progressPercent}%` }} />
          </div>
          <small>Możesz zostać na tej stronie — statusy i wynik końcowy odświeżą się automatycznie.</small>
        </section>
      ) : null}

      {error ? <div className="alert">{error}</div> : null}
      {notice && !error ? <div className="syncCompleteNotice">✓ {notice}</div> : null}
      {result ? (
        <div className={`globalSyncResult ${result.status}`}>
          <strong>Wynik zbiorczy: {STATUS_LABELS[result.status] ?? result.status}</strong>
          <ul>{result.results.map((item) => <li key={item.platform}><b>{PLATFORM_LABELS[item.platform]}:</b> {item.message}</li>)}</ul>
        </div>
      ) : null}

      <section className="syncPlatformGrid">
        {(overview?.platforms ?? []).map((item) => {
          const connectPath = item.platform === "youtube" ? "/api/integrations/youtube/connect" : `/api/platforms/meta/connect?target=${item.platform}`;
          return (
            <article key={item.platform} className={`syncPlatformCard${busy === item.platform || item.last_sync_status === "running" ? " syncing" : ""}`}>
              <div className="syncPlatformHeading">
                <span className={`platformStatusIcon ${item.platform}`}>{ICONS[item.platform]}</span>
                <div><h3>{PLATFORM_LABELS[item.platform]}</h3><p>{item.display_name ?? (item.connected ? "Połączono" : "Niepołączono")}</p></div>
                <span className={`pill ${item.connected ? "success" : ""}`}>{item.connected ? "Połączono" : "Niepołączono"}</span>
              </div>
              <dl className="syncPlatformFacts">
                <div><dt>Ostatnia synchronizacja</dt><dd>{dateTime(item.last_synced_at)}</dd></div>
                <div><dt>Status</dt><dd className={`syncStatusText ${item.last_sync_status ?? "idle"}`}>{STATUS_LABELS[item.last_sync_status ?? ""] ?? "Brak historii"}</dd></div>
                <div><dt>Harmonogram</dt><dd>{item.scheduler_enabled ? `Co ${item.scheduler_interval_hours} godz.` : "Wyłączony"}</dd></div>
                <div><dt>Następny sync</dt><dd>{item.scheduler_enabled ? dateTime(item.next_scheduled_sync_at) : "—"}</dd></div>
              </dl>
              {item.last_sync_error ? <div className="syncCardError"><strong>Ostatni błąd</strong><span>{item.last_sync_error}</span></div> : null}
              <div className="actions">
                {item.connected ? (
                  <>
                    <button className="button" onClick={() => syncOne(item.platform)} disabled={busy !== null}>{busy === item.platform ? "Synchronizuję…" : "Synchronizuj"}</button>
                    <button className="button secondary" onClick={() => disconnect(item.platform)} disabled={busy !== null}>Odłącz</button>
                  </>
                ) : (
                  <a className={`button ${!item.configured ? "disabled" : ""}`} href={`${API_URL}${connectPath}`}>Połącz</a>
                )}
              </div>
            </article>
          );
        })}
        <article className="syncPlatformCard planned">
          <div className="syncPlatformHeading"><span className="platformStatusIcon tiktok">♪</span><div><h3>TikTok</h3><p>Adapter planowany</p></div><span className="pill">Wkrótce</span></div>
          <p className="muted">Karta korzysta z tego samego układu i jest gotowa na przyszłą integrację.</p>
        </article>
      </section>

      <section className="libraryPanel">
        <div className="libraryHeading"><div><p className="eyebrow">HISTORIA</p><h2>Ostatnie synchronizacje</h2></div></div>
        {!overview ? <div className="empty">Ładuję historię…</div> : overview.history.length === 0 ? (
          <div className="emptyState"><h3>Brak historii</h3><p>Uruchom pierwszą synchronizację, aby zobaczyć jej wynik.</p></div>
        ) : (
          <div className="syncHistoryList">
            {overview.history.map((run) => (
              <div key={run.id} className="syncHistoryRow">
                <span className={`platformStatusIcon ${run.platform}`}>{ICONS[run.platform]}</span>
                <div><strong>{PLATFORM_LABELS[run.platform]} · {run.kind === "comments" ? "komentarze" : "treści"}</strong><small>{dateTime(run.started_at)}</small></div>
                <span className={`syncStatusTag ${run.status}`}>{STATUS_LABELS[run.status] ?? run.status}</span>
                <span>{run.kind === "comments" ? `${run.comments_imported} komentarzy` : `${run.imported_items} nowych · ${run.snapshots_created} migawek`}</span>
                <span className="syncHistoryError">{run.error_message ?? "Bez błędów"}</span>
              </div>
            ))}
          </div>
        )}
      </section>
    </>
  );
}
