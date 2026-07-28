import { YoutubePanel } from "../components/youtube-panel";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://127.0.0.1:8000";

type Reel = { id: number; title: string; category: string; hook: string | null };

async function getReels(): Promise<Reel[]> {
  try {
    const response = await fetch(`${INTERNAL_API_URL}/api/reels`, { cache: "no-store" });
    return response.ok ? response.json() : [];
  } catch { return []; }
}

export default async function Home() {
  const reels = await getReels();
  return (
    <main>
      <section className="hero">
        <p className="eyebrow">359° / ŁUKASZ OLEŚ</p>
        <h1>Reels Command Center</h1>
        <p className="lead">Sprint 2: prawdziwy fundament integracji YouTube.</p>
      </section>

      <section className="grid">
        <article className="card"><span>OAuth</span><strong>Google</strong><small>Tokeny szyfrowane lokalnie</small></article>
        <article className="card"><span>Synchronizacja</span><strong>YouTube</strong><small>Kanał, filmy i metryki</small></article>
        <article className="card"><span>Historia</span><strong>Migawki</strong><small>Nowy odczyt przy każdym syncu</small></article>
      </section>

      <YoutubePanel />

      <section className="panel">
        <div className="panelHeader"><div><p className="eyebrow">CONTENT LIBRARY</p><h2>Rolki ręczne</h2></div><span className="pill">{reels.length} zapisanych</span></div>
        {reels.length === 0 ? <div className="empty">Baza ręcznych rolek jest pusta.</div> : <div className="list">{reels.map((reel) => <article className="row" key={reel.id}><div><strong>{reel.title}</strong><p>{reel.hook ?? "Brak hooka"}</p></div><span className="pill">{reel.category}</span></article>)}</div>}
      </section>
    </main>
  );
}
