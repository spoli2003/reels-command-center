"use client";

import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

type Status = {
  configured: boolean;
  connected: boolean;
  channel_title: string | null;
  channel_id: string | null;
  last_synced_at: string | null;
  video_count: number;
  message: string;
};

type Video = {
  youtube_video_id: string;
  title: string;
  published_at: string;
  thumbnail_url: string | null;
  duration_seconds: number | null;
  is_short_candidate: boolean;
  views: number;
  likes: number;
  comments: number;
};

export function YoutubePanel() {
  const [status, setStatus] = useState<Status | null>(null);
  const [videos, setVideos] = useState<Video[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setError("");
    try {
      const [statusResponse, videosResponse] = await Promise.all([
        fetch(`${API_URL}/api/integrations/youtube/status`, { cache: "no-store" }),
        fetch(`${API_URL}/api/integrations/youtube/videos`, { cache: "no-store" }),
      ]);
      setStatus(await statusResponse.json());
      setVideos(videosResponse.ok ? await videosResponse.json() : []);
    } catch {
      setError("Backend nie odpowiada. Sprawdź, czy Docker działa.");
    }
  }

  useEffect(() => { void load(); }, []);

  async function synchronize() {
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${API_URL}/api/integrations/youtube/sync`, { method: "POST" });
      if (!response.ok) {
        const body = await response.json();
        throw new Error(body.detail ?? "Synchronizacja nie powiodła się");
      }
      await load();
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
  }

  return (
    <section className="panel">
      <div className="panelHeader">
        <div>
          <p className="eyebrow">INTEGRACJA</p>
          <h2>YouTube</h2>
          <p className="muted">Oficjalny OAuth, kanał, filmy i migawki statystyk.</p>
        </div>
        <span className={`pill ${status?.connected ? "success" : ""}`}>
          {status?.connected ? "Połączono" : "Niepołączono"}
        </span>
      </div>

      {error && <div className="alert">{error}</div>}

      {!status ? (
        <div className="empty">Sprawdzam konfigurację…</div>
      ) : !status.connected ? (
        <div className="integrationBox">
          <div>
            <strong>{status.message}</strong>
            <p>Plik OAuth umieść w <code>backend/secrets/google_client_secret.json</code>.</p>
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
              <p>{status.video_count} zaimportowanych filmów · ostatnia synchronizacja: {status.last_synced_at ? new Date(status.last_synced_at).toLocaleString("pl-PL") : "jeszcze nie wykonano"}</p>
            </div>
            <div className="actions">
              <button className="button" onClick={synchronize} disabled={busy}>{busy ? "Synchronizuję…" : "Synchronizuj"}</button>
              <button className="button secondary" onClick={disconnect}>Odłącz</button>
            </div>
          </div>
          <div className="videoGrid">
            {videos.slice(0, 12).map((video) => (
              <article className="videoCard" key={video.youtube_video_id}>
                {video.thumbnail_url ? <img src={video.thumbnail_url} alt="" /> : <div className="thumbnailPlaceholder" />}
                <div>
                  <span className="micro">{video.is_short_candidate ? "SHORT ≤ 180 S" : "FILM"}</span>
                  <strong>{video.title}</strong>
                  <p>{video.views.toLocaleString("pl-PL")} wyświetleń · {video.likes.toLocaleString("pl-PL")} polubień · {video.comments.toLocaleString("pl-PL")} komentarzy</p>
                </div>
              </article>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
