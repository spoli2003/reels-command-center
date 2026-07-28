"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

export type Snapshot = {
  views: number;
  likes: number;
  comments: number;
  shares: number;
  saves: number;
  followers_gained?: number | null;
};

export type Publication = {
  id: number;
  platform: string;
  external_id: string;
  url?: string | null;
  published_at?: string | null;
  latest_metrics?: Snapshot | null;
};

export type Video = {
  id: number;
  public_id: string;
  title: string;
  description: string;
  category?: string | null;
  duration_seconds?: number | null;
  language: string;
  created_at: string;
  updated_at: string;
  publications: Publication[];
  total_views: number;
  total_interactions: number;
  engagement_rate: number;
};

const PLATFORM_LABELS: Record<string, string> = {
  facebook: "F",
  instagram: "I",
  tiktok: "T",
  youtube: "Y",
};

function compact(value: number) {
  return new Intl.NumberFormat("pl-PL", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

function dateLabel(value: string) {
  return new Intl.DateTimeFormat("pl-PL", { day: "2-digit", month: "short", year: "numeric" }).format(new Date(value));
}

export function VideoLibrary({ initialVideos }: { initialVideos: Video[] }) {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");
  const [platform, setPlatform] = useState("all");
  const [sort, setSort] = useState("views");

  const categories = useMemo(
    () => Array.from(new Set(initialVideos.map((video) => video.category).filter(Boolean) as string[])).sort(),
    [initialVideos],
  );

  const videos = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase("pl");
    const result = initialVideos.filter((video) => {
      const matchesQuery = !normalized || `${video.title} ${video.description} ${video.category ?? ""}`.toLocaleLowerCase("pl").includes(normalized);
      const matchesCategory = category === "all" || video.category === category;
      const matchesPlatform = platform === "all" || video.publications.some((item) => item.platform === platform);
      return matchesQuery && matchesCategory && matchesPlatform;
    });
    return [...result].sort((a, b) => {
      if (sort === "title") return a.title.localeCompare(b.title, "pl");
      if (sort === "date") return +new Date(b.created_at) - +new Date(a.created_at);
      if (sort === "er") return b.engagement_rate - a.engagement_rate;
      return b.total_views - a.total_views;
    });
  }, [initialVideos, query, category, platform, sort]);

  const totalViews = initialVideos.reduce((sum, video) => sum + video.total_views, 0);
  const totalInteractions = initialVideos.reduce((sum, video) => sum + video.total_interactions, 0);
  const connectedPlatforms = new Set(initialVideos.flatMap((video) => video.publications.map((item) => item.platform))).size;

  return (
    <>
      <section className="statsGrid">
        <article className="metricCard"><span>Filmy</span><strong>{initialVideos.length}</strong><small>w bibliotece</small></article>
        <article className="metricCard"><span>Wyświetlenia</span><strong>{compact(totalViews)}</strong><small>łącznie na platformach</small></article>
        <article className="metricCard"><span>Interakcje</span><strong>{compact(totalInteractions)}</strong><small>reakcje, komentarze, udostępnienia</small></article>
        <article className="metricCard"><span>Platformy</span><strong>{connectedPlatforms}</strong><small>z zapisanymi publikacjami</small></article>
      </section>

      <section className="libraryPanel">
        <div className="libraryHeading">
          <div><p className="eyebrow">CONTENT LIBRARY</p><h2>Wszystkie filmy</h2><p className="muted">Jedna rolka, wszystkie publikacje i wspólny wynik.</p></div>
          <Link className="primaryButton" href="/">+ Nowy film</Link>
        </div>

        <div className="toolbar">
          <input aria-label="Szukaj" className="searchInput" placeholder="Szukaj tytułu, tematu lub kategorii…" value={query} onChange={(event) => setQuery(event.target.value)} />
          <select value={category} onChange={(event) => setCategory(event.target.value)}><option value="all">Wszystkie kategorie</option>{categories.map((item) => <option key={item} value={item}>{item}</option>)}</select>
          <select value={platform} onChange={(event) => setPlatform(event.target.value)}><option value="all">Wszystkie platformy</option><option value="facebook">Facebook</option><option value="instagram">Instagram</option><option value="tiktok">TikTok</option><option value="youtube">YouTube</option></select>
          <select value={sort} onChange={(event) => setSort(event.target.value)}><option value="views">Najwięcej wyświetleń</option><option value="er">Najwyższy ER</option><option value="date">Najnowsze</option><option value="title">Alfabetycznie</option></select>
        </div>

        {videos.length === 0 ? (
          <div className="emptyState"><div className="emptyIcon">◫</div><h3>Nie znaleziono filmów</h3><p>Zmień filtry albo dodaj pierwszy film przez API.</p></div>
        ) : (
          <div className="videoTable">
            <div className="tableHeader"><span>Treść</span><span>Platformy</span><span>Wyświetlenia</span><span>Interakcje</span><span>ER</span><span>Data</span></div>
            {videos.map((video) => (
              <Link href={`/videos/${video.id}`} className="tableRow" key={video.id}>
                <div className="videoIdentity"><div className="videoThumb">{video.title.slice(0, 1).toUpperCase()}</div><div><strong>{video.title}</strong><p>{video.category ?? "Bez kategorii"} · {video.public_id.slice(0, 8)}</p></div></div>
                <div className="platforms">{video.publications.length ? video.publications.map((item) => <span title={item.platform} key={item.id}>{PLATFORM_LABELS[item.platform] ?? item.platform.slice(0, 1).toUpperCase()}</span>) : <small>—</small>}</div>
                <strong>{compact(video.total_views)}</strong>
                <span>{compact(video.total_interactions)}</span>
                <span>{video.engagement_rate.toFixed(2)}%</span>
                <span className="dateCell">{dateLabel(video.created_at)}</span>
              </Link>
            ))}
          </div>
        )}
        <div className="resultCount">Wyświetlono {videos.length} z {initialVideos.length} filmów</div>
      </section>
    </>
  );
}
