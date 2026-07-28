import Link from "next/link";
import { YoutubePanel } from "../components/youtube-panel";
import type { Video } from "../components/video-library";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://127.0.0.1:8000";

async function getVideos(): Promise<Video[]> {
  try {
    const response = await fetch(`${INTERNAL_API_URL}/api/content/videos`, { cache: "no-store" });
    return response.ok ? response.json() : [];
  } catch { return []; }
}

function compact(value: number) { return new Intl.NumberFormat("pl-PL", { notation: "compact", maximumFractionDigits: 1 }).format(value); }

export default async function Home() {
  const videos = await getVideos();
  const views = videos.reduce((sum, item) => sum + item.total_views, 0);
  const interactions = videos.reduce((sum, item) => sum + item.total_interactions, 0);
  const top = [...videos].sort((a,b) => b.total_views - a.total_views).slice(0, 5);
  return (
    <div className="appShell">
      <aside className="sidebar"><Link className="brand" href="/"><span>359°</span><strong>RCC</strong></Link><nav><Link className="active" href="/">Dashboard</Link><Link href="/videos">Filmy</Link><a href="#">Analytics</a><a href="#">AI</a><a href="#">Business</a><a href="#">Integracje</a></nav><div className="sidebarFooter"><span className="statusDot" />System lokalny działa</div></aside>
      <main className="workspace">
        <header className="topbar"><div><p className="eyebrow">359° / ŁUKASZ OLEŚ</p><h1>Centrum dowodzenia</h1><p className="muted">Jedno miejsce dla wszystkich treści i platform.</p></div><Link className="primaryButton" href="/videos">Otwórz bibliotekę</Link></header>
        <section className="statsGrid"><article className="metricCard featured"><span>Łączne wyświetlenia</span><strong>{compact(views)}</strong><small>wszystkie platformy</small></article><article className="metricCard"><span>Interakcje</span><strong>{compact(interactions)}</strong><small>łączny wynik</small></article><article className="metricCard"><span>Filmy</span><strong>{videos.length}</strong><small>w bibliotece</small></article><article className="metricCard"><span>Średni ER</span><strong>{views ? ((interactions/views)*100).toFixed(2) : "0.00"}%</strong><small>dla całej biblioteki</small></article></section>
        <section className="dashboardGrid"><div className="libraryPanel"><div className="libraryHeading"><div><p className="eyebrow">RANKING</p><h2>Najmocniejsze filmy</h2></div><Link className="textLink" href="/videos">Zobacz wszystkie →</Link></div>{top.length === 0 ? <div className="emptyState"><h3>Brak danych</h3><p>Dodaj pierwszy film w Swaggerze lub zsynchronizuj YouTube.</p></div> : <div className="rankingList">{top.map((video,index) => <Link href={`/videos/${video.id}`} className="rankingRow" key={video.id}><span className="rank">{String(index+1).padStart(2,"0")}</span><div><strong>{video.title}</strong><p>{video.category ?? "Bez kategorii"}</p></div><strong>{compact(video.total_views)}</strong></Link>)}</div>}</div><div className="integrationColumn"><YoutubePanel /></div></section>
      </main>
    </div>
  );
}
