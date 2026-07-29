"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

export type PickableVideo = { youtube_video_id: string; title: string; published_at: string };

export function VideoPicker({
  videos,
  selected,
  onToggle,
  max = 6,
}: {
  videos: PickableVideo[];
  selected: string[];
  onToggle: (youtubeVideoId: string) => void;
  max?: number;
}) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase("pl");
    if (!normalized) return videos;
    return videos.filter((video) => video.title.toLocaleLowerCase("pl").includes(normalized));
  }, [videos, query]);

  return (
    <div className="videoPicker">
      <input
        className="searchInput"
        placeholder="Szukaj filmu do porównania…"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        aria-label="Szukaj filmu"
      />
      <div className="videoPickerList">
        {filtered.map((video) => {
          const checked = selected.includes(video.youtube_video_id);
          const disabled = !checked && selected.length >= max;
          return (
            <div key={video.youtube_video_id} className={checked ? "videoPickerRow checked" : "videoPickerRow"}>
              <label className="videoPickerToggle">
                <input
                  type="checkbox"
                  checked={checked}
                  disabled={disabled}
                  onChange={() => onToggle(video.youtube_video_id)}
                />
                <span>{video.title}</span>
                <small>{new Date(video.published_at).toLocaleDateString("pl-PL")}</small>
              </label>
              <Link
                href={`/youtube/videos/${video.youtube_video_id}`}
                className="videoPickerDetailLink"
                title="Otwórz szczegóły filmu"
                aria-label={`Otwórz szczegóły filmu: ${video.title}`}
              >
                Szczegóły
              </Link>
            </div>
          );
        })}
        {filtered.length === 0 ? <p className="muted">Brak wyników.</p> : null}
      </div>
      <p className="muted">
        {selected.length}/{max} wybranych filmów
      </p>
    </div>
  );
}
