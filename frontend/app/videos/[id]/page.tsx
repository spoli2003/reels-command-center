import Link from "next/link";
import { notFound } from "next/navigation";
import type { Video } from "../../../components/video-library";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://127.0.0.1:8000";

async function getVideo(id: string): Promise<Video | null> {
  try {
    const response = await fetch(`${INTERNAL_API_URL}/api/content/videos/${id}`, { cache: "no-store" });
    return response.ok ? response.json() : null;
  } catch { return null; }
}

function formatNumber(value: number) { return new Intl.NumberFormat("pl-PL").format(value); }

export default async function VideoPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const video = await getVideo(id);
  if (!video) notFound();
  return (
    <div className="appShell">
      <aside className="sidebar"><Link className="brand" href="/"><span>359°</span><strong>RCC</strong></Link><nav><Link href="/">Dashboard</Link><Link className="active" href="/videos">Filmy</Link><a href="#">Analytics</a><a href="#">AI</a><a href="#">Business</a><a href="#">Integracje</a></nav><div className="sidebarFooter"><span className="statusDot" />System lokalny działa</div></aside>
      <main className="workspace">
        <Link className="backLink" href="/videos">← Wróć do biblioteki</Link>
        <section className="videoHero"><div className="largeThumb">{video.title.slice(0,1).toUpperCase()}</div><div><p className="eyebrow">{video.category ?? "BEZ KATEGORII"}</p><h1>{video.title}</h1><p className="muted">{video.description || "Brak opisu filmu."}</p><div className="metaLine"><span>{video.public_id}</span>{video.duration_seconds ? <span>{video.duration_seconds} s</span> : null}<span>{video.language.toUpperCase()}</span></div></div></section>
        <section className="statsGrid detailStats"><article className="metricCard"><span>Wyświetlenia</span><strong>{formatNumber(video.total_views)}</strong></article><article className="metricCard"><span>Interakcje</span><strong>{formatNumber(video.total_interactions)}</strong></article><article className="metricCard"><span>Engagement rate</span><strong>{video.engagement_rate.toFixed(2)}%</strong></article><article className="metricCard"><span>Publikacje</span><strong>{video.publications.length}</strong></article></section>
        <section className="libraryPanel"><div className="libraryHeading"><div><p className="eyebrow">DISTRIBUTION</p><h2>Publikacje</h2></div></div>{video.publications.length === 0 ? <div className="emptyState"><h3>Brak publikacji</h3><p>Dodaj publikację przez endpoint API.</p></div> : <div className="publicationGrid">{video.publications.map((publication) => <article className="publicationCard" key={publication.id}><div className="publicationTop"><span className="platformName">{publication.platform}</span>{publication.url ? <a href={publication.url} target="_blank" rel="noreferrer">Otwórz ↗</a> : null}</div><strong>{publication.latest_metrics ? formatNumber(publication.latest_metrics.views) : "0"}</strong><small>wyświetleń</small><div className="publicationMetrics"><span>👍 {formatNumber(publication.latest_metrics?.likes ?? 0)}</span><span>💬 {formatNumber(publication.latest_metrics?.comments ?? 0)}</span><span>↗ {formatNumber(publication.latest_metrics?.shares ?? 0)}</span></div></article>)}</div>}</section>
      </main>
    </div>
  );
}
