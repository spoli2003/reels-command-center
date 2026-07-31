"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import type { PlatformKey } from "../lib/platform-api";

export type PickablePlatformVideo = { external_id: string; title: string; published_at: string | null };

/** Same UX/classes as components/video-picker.tsx, keyed by external_id and
 * linking into /platforms/{platform}/videos/{id}. */
export function PlatformVideoPicker({
  platform,
  videos,
  selected,
  onToggle,
  max = 6,
}: {
  platform: PlatformKey;
  videos: PickablePlatformVideo[];
  selected: string[];
  onToggle: (externalId: string) => void;
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
        placeholder="Szukaj materiału do porównania…"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        aria-label="Szukaj materiału"
      />
      <div className="videoPickerList">
        {filtered.map((video) => {
          const checked = selected.includes(video.external_id);
          const disabled = !checked && selected.length >= max;
          return (
            <div key={video.external_id} className={checked ? "videoPickerRow checked" : "videoPickerRow"}>
              <label className="videoPickerToggle">
                <input type="checkbox" checked={checked} disabled={disabled} onChange={() => onToggle(video.external_id)} />
                <span>{video.title}</span>
                <small>{video.published_at ? new Date(video.published_at).toLocaleDateString("pl-PL") : "—"}</small>
              </label>
              <Link
                href={`/platforms/${platform}/videos/${video.external_id}`}
                className="videoPickerDetailLink"
                title="Otwórz szczegóły"
                aria-label={`Otwórz szczegóły: ${video.title}`}
              >
                Szczegóły
              </Link>
            </div>
          );
        })}
        {filtered.length === 0 ? <p className="muted">Brak wyników.</p> : null}
      </div>
      <p className="muted">
        {selected.length}/{max} wybranych pozycji
      </p>
    </div>
  );
}
