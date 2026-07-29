"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import type { YoutubeStatus } from "../lib/youtube-api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

const SYNC_STATUS_LABELS: Record<string, string> = {
  success: "Udana",
  partial: "Częściowo udana",
  failed: "Nieudana",
};

export function YoutubePanel() {
  const router = useRouter();
  const [status, setStatus] = useState<YoutubeStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [lastSyncFeedback, setLastSyncFeedback] = useState("");

  async function load() {
    setError("");
    try {
      const response = await fetch(`${API_URL}/api/integrations/youtube/status`, { cache: "no-store" });
      setStatus(await response.json());
    } catch {
      setError("Backend nie odpowiada. Sprawdź, czy Docker działa.");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function synchronize() {
    setBusy(true);
    setError("");
    setLastSyncFeedback("");
    try {
      const response = await fetch(`${API_URL}/api/integrations/youtube/sync`, { method: "POST" });
      if (!response.ok) {
        const body = await response.json();
        throw new Error(body.detail ?? "Synchronizacja nie powiodła się");
      }
      const result = await response.json();
      setLastSyncFeedback(`Zaimportowano ${result.imported_videos} nowych filmów. Zapisano migawki dla wszystkich filmów kanału.`);
      await load();
      // Re-render every server component on the current page (Home's header,
      // any other page embedding this panel) with fresh data from the backend —
      // without this, only this client component's own state would update,
      // leaving server-rendered sync timestamps elsewhere on the page stale.
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Synchronizacja nie powiodła się");
    } finally {
      setBusy(false);
    }
  }

  async function disconnect() {
    if (!confirm("Odłączyć lokalnie konto YouTube i usunąć zapisane tokeny?")) return;
    await fetch(`${API_URL}/api/integrations/youtube/disconnect`, { method: "DELETE" });
    await load();
    router.refresh();
  }

  return (
    <section className="panel">
      <div className="panelHeader">
        <div>
          <p className="eyebrow">SYNCHRONIZACJA</p>
          <h2>YouTube</h2>
          <p className="muted">Oficjalny OAuth, kanał, filmy i migawki statystyk.</p>
        </div>
        <span className={`pill ${status?.connected ? "success" : ""}`}>{status?.connected ? "Połączono" : "Niepołączono"}</span>
      </div>

      {error && <div className="alert">{error}</div>}
      {lastSyncFeedback && !error ? <div className="syncFeedback">✓ {lastSyncFeedback}</div> : null}

      {!status ? (
        <div className="empty">Sprawdzam konfigurację…</div>
      ) : !status.connected ? (
        <div className="integrationBox">
          <div>
            <strong>{status.message}</strong>
            <p>
              Plik OAuth umieść w <code>backend/secrets/google_client_secret.json</code>.
            </p>
          </div>
          <a className={`button ${!status.configured ? "disabled" : ""}`} href={`${API_URL}/api/integrations/youtube/connect`}>
            Połącz konto Google
          </a>
        </div>
      ) : (
        <>
          <div className="integrationBox">
            <div>
              <strong>{status.channel_title}</strong>
              <p>
                {status.video_count} zaimportowanych filmów · ostatnia synchronizacja:{" "}
                {status.last_synced_at ? new Date(status.last_synced_at).toLocaleString("pl-PL") : "jeszcze nie wykonano"}
              </p>
            </div>
            <div className="actions">
              <button className="button" onClick={synchronize} disabled={busy}>
                {busy ? "Synchronizuję…" : "Synchronizuj teraz"}
              </button>
              <button className="button secondary" onClick={disconnect}>
                Odłącz
              </button>
            </div>
          </div>

          <div className="syncDetailRow">
            <span title="Uprawnienia OAuth aktualnie przyznane RCC przez to konto Google.">Uprawnienia</span>
            <strong className={`syncStatusTag ${status.comments_scope_granted ? "success" : "partial"}`}>
              {status.comments_scope_granted ? "Analityka + Komentarze" : "Tylko analityka (bez komentarzy)"}
            </strong>
          </div>
          {status.comments_reconnect_required ? (
            <div className="alert informational">
              Aby korzystać ze Skrzynki komentarzy, połącz konto ponownie i zaakceptuj dodatkowe uprawnienie do odczytu i publikowania
              komentarzy. Istniejące dane analityczne (filmy, historia, synchronizacje) zostaną zachowane — ponowne połączenie tylko
              odświeży token dostępu.{" "}
              <a href={`${API_URL}/api/integrations/youtube/connect`} className="textLink">
                Połącz ponownie →
              </a>
            </div>
          ) : null}

          {status.last_sync_status ? (
            <div className="syncDetails">
              <div className="syncDetailRow">
                <span>Status ostatniej synchronizacji</span>
                <strong className={`syncStatusTag ${status.last_sync_status}`}>
                  {SYNC_STATUS_LABELS[status.last_sync_status] ?? status.last_sync_status}
                </strong>
              </div>
              <div className="syncDetailRow">
                <span>Czas trwania</span>
                <strong>{status.last_sync_duration_seconds !== null ? `${status.last_sync_duration_seconds.toFixed(1)} s` : "—"}</strong>
              </div>
              <div className="syncDetailRow">
                <span>Nowe filmy / zaktualizowane</span>
                <strong>
                  {status.last_sync_videos_new ?? 0} / {status.last_sync_videos_updated ?? 0}
                </strong>
              </div>
              <div className="syncDetailRow">
                <span>Zapisane migawki metryk</span>
                <strong>{status.last_sync_snapshots_created ?? 0}</strong>
              </div>
              <div className="syncDetailRow">
                <span>Pominięte duplikaty migawek</span>
                <strong title="Migawki pominięte jako duplikaty tej samej synchronizacji (Sprint 6, ochrona przed powtórnym zapisem)">
                  {status.last_sync_snapshots_deduplicated ?? 0}
                </strong>
              </div>
              {status.last_sync_videos_failed ? (
                <div className="syncDetailRow">
                  <span>Filmy z błędem przetwarzania</span>
                  <strong className="syncStatusTag partial">{status.last_sync_videos_failed}</strong>
                </div>
              ) : null}
              {status.last_sync_error ? (
                <div className="syncDetailRow">
                  <span>Błąd</span>
                  <strong className="syncStatusTag failed">{status.last_sync_error}</strong>
                </div>
              ) : null}
              <div className="syncDetailRow">
                <span>Harmonogram automatyczny</span>
                <strong className={`syncStatusTag ${status.automatic_sync_enabled ? "success" : ""}`}>
                  {status.automatic_sync_enabled ? `Aktywny · co ${status.automatic_sync_interval_hours}h` : "Wyłączony"}
                </strong>
              </div>
              {status.automatic_sync_enabled && status.automatic_sync_next_at ? (
                <div className="syncDetailRow">
                  <span>Następna planowana synchronizacja</span>
                  <strong>{new Date(status.automatic_sync_next_at).toLocaleString("pl-PL")}</strong>
                </div>
              ) : null}
              <p className="muted syncAutoNote">{status.automatic_sync_note}</p>
            </div>
          ) : null}

          <Link className="textLink" href="/youtube" style={{ display: "inline-block", marginTop: 14 }}>
            Pełny dashboard analityczny →
          </Link>
        </>
      )}
    </section>
  );
}
