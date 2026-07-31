"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { PLATFORM_LABELS, type PlatformKey, type PlatformStatus } from "../lib/platform-api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const SYNC_STATUS_LABELS: Record<string, string> = { success: "Udana", partial: "Częściowo udana", failed: "Nieudana" };

/** Connect/sync panel for Facebook and Instagram — mirrors YoutubePanel's UX
 * (same classes, same flow) but drives the generic Meta OAuth + /api/platforms/*
 * endpoints (ADR-021) instead of the YouTube-specific ones. */
export function MetaPlatformPanel({ platform }: { platform: Extract<PlatformKey, "facebook" | "instagram"> }) {
  const router = useRouter();
  const [status, setStatus] = useState<PlatformStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [lastSyncFeedback, setLastSyncFeedback] = useState("");

  async function load() {
    setError("");
    try {
      const response = await fetch(`${API_URL}/api/platforms/${platform}/status`, { cache: "no-store" });
      setStatus(await response.json());
    } catch {
      setError("Backend nie odpowiada. Sprawdź, czy Docker działa.");
    }
  }

  useEffect(() => {
    void load();
    const params = new URLSearchParams(window.location.search);
    if (params.get("connected") === "1") {
      const sync = params.get("sync");
      const imported = params.get("imported") ?? "0";
      const comments = params.get("comments") ?? "0";
      if (sync === "success" || sync === "partial") {
        setLastSyncFeedback(`Konto połączono. Pierwszy sync: ${imported} nowych materiałów, ${comments} nowych komentarzy.`);
      } else if (sync === "failed") {
        setError(params.get("message") ?? "Konto połączono, ale pierwszy sync nie powiódł się. Możesz ponowić go poniżej.");
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function synchronize() {
    setBusy(true);
    setError("");
    setLastSyncFeedback("");
    try {
      const response = await fetch(`${API_URL}/api/platforms/${platform}/sync`, { method: "POST" });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail ?? "Synchronizacja nie powiodła się");
      }
      const result = await response.json();
      setLastSyncFeedback(
        `Zaimportowano ${result.imported_items} nowych pozycji. Zapisano ${result.snapshots_created} nowych migawek i pobrano ${result.threads_discovered} wątków komentarzy.${result.comment_sync_error ? ` ${result.comment_sync_error}` : ""}`,
      );
      await load();
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Synchronizacja nie powiodła się");
    } finally {
      setBusy(false);
    }
  }

  async function disconnect() {
    if (!confirm(`Odłączyć lokalnie konto ${PLATFORM_LABELS[platform]} i usunąć zapisane tokeny?`)) return;
    await fetch(`${API_URL}/api/platforms/${platform}/disconnect`, { method: "DELETE" });
    await load();
    router.refresh();
  }

  return (
    <section className="panel">
      <div className="panelHeader">
        <div>
          <p className="eyebrow">SYNCHRONIZACJA</p>
          <h2>{PLATFORM_LABELS[platform]}</h2>
          <p className="muted">
            {platform === "facebook" ? "Strona na Facebooku — posty, filmy i Reelsy." : "Konto profesjonalne na Instagramie — Reelsy i posty."}
          </p>
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
            {!status.configured ? (
              <p>
                Skonfiguruj <code>META_APP_ID</code> / <code>META_APP_SECRET</code> w backendzie, aby włączyć połączenie.
              </p>
            ) : (
              <div>
                <p>Połącz Stronę na Facebooku {platform === "instagram" ? "z podłączonym kontem Instagram Business lub Creator" : ""}, aby zacząć synchronizację.</p>
                {platform === "instagram" ? (
                  <p className="muted">Konfiguracja Meta musi przyznać: {status.required_permissions.join(", ")}.</p>
                ) : null}
              </div>
            )}
          </div>
          <a className={`button ${!status.configured ? "disabled" : ""}`} href={`${API_URL}/api/platforms/meta/connect?target=${platform}`}>
            Połącz {PLATFORM_LABELS[platform]}
          </a>
        </div>
      ) : (
        <>
          <div className="integrationBox">
            <div>
              <strong>{status.display_name}</strong>
              <p>
                {status.video_count} zaimportowanych pozycji · ostatnia synchronizacja:{" "}
                {status.last_synced_at ? new Date(status.last_synced_at).toLocaleString("pl-PL") : "jeszcze nie wykonano"}
              </p>
            </div>
            <div className="actions">
              <button className="button" onClick={synchronize} disabled={busy || status.missing_permissions.length > 0}>
                {busy ? "Synchronizuję…" : "Synchronizuj teraz"}
              </button>
              {status.missing_permissions.length > 0 ? (
                <a className="button" href={`${API_URL}/api/platforms/meta/connect?target=${platform}`}>
                  Połącz ponownie
                </a>
              ) : null}
              <button className="button secondary" onClick={disconnect}>
                Odłącz
              </button>
            </div>
          </div>

          {status.missing_permissions.length > 0 ? (
            <div className="alert">
              <strong>Brakujące uprawnienia Meta: {status.missing_permissions.join(", ")}.</strong>{" "}
              Dodaj je w Facebook Login for Business → Configurations → Permissions, usuń stare RCC z Integracji biznesowych i połącz konto ponownie.
            </div>
          ) : null}

          {status.missing_permissions.length === 0 && status.missing_optional_permissions.length > 0 ? (
            <div className="alert">
              <strong>{PLATFORM_LABELS[platform]} jest połączony, a synchronizacja treści działa.</strong>{" "}
              Komentarze są obecnie pomijane, ponieważ token nie ma opcjonalnych uprawnień: {status.missing_optional_permissions.join(", ")}.
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
              {status.last_sync_error ? (
                <div className="syncDetailRow">
                  <span>Błąd</span>
                  <strong className="syncStatusTag failed">{status.last_sync_error}</strong>
                </div>
              ) : null}
              <div className="syncDetailRow">
                <span>Komentarze</span>
                <strong>
                  {status.last_comments_synced_at
                    ? `${SYNC_STATUS_LABELS[status.last_comments_sync_status ?? ""] ?? status.last_comments_sync_status} · ${new Date(status.last_comments_synced_at).toLocaleString("pl-PL")}`
                    : "jeszcze nie synchronizowano"}
                </strong>
              </div>
              <div className="syncDetailRow">
                <span>Automatyczna synchronizacja</span>
                <strong>
                  {status.scheduler_enabled
                    ? status.next_scheduled_sync_at
                      ? `włączona · następna ${new Date(status.next_scheduled_sync_at).toLocaleString("pl-PL")}`
                      : "włączona · oczekuje na pierwszy cykl"
                    : "wyłączona (META_SYNC_ENABLED=false)"}
                </strong>
              </div>
            </div>
          ) : null}
        </>
      )}
    </section>
  );
}
