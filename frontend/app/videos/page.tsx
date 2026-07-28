import Link from "next/link";
import { VideoLibrary, type Video } from "../../components/video-library";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://127.0.0.1:8000";

async function getVideos(): Promise<Video[]> {
  try {
    const response = await fetch(`${INTERNAL_API_URL}/api/content/videos`, { cache: "no-store" });
    return response.ok ? response.json() : [];
  } catch {
    return [];
  }
}

export default async function VideosPage() {
  const videos = await getVideos();
  return (
    <div className="appShell">
      <aside className="sidebar">
        <Link className="brand" href="/"><span>359°</span><strong>RCC</strong></Link>
        <nav><Link href="/">Dashboard</Link><Link className="active" href="/videos">Filmy</Link><a href="#">Analytics</a><a href="#">AI</a><a href="#">Business</a><a href="#">Integracje</a></nav>
        <div className="sidebarFooter"><span className="statusDot" />System lokalny działa</div>
      </aside>
      <main className="workspace">
        <header className="topbar"><div><p className="eyebrow">REELS COMMAND CENTER</p><h1>Biblioteka filmów</h1></div><div className="topActions"><span className="localBadge">LOCAL</span></div></header>
        <VideoLibrary initialVideos={videos} />
      </main>
    </div>
  );
}
