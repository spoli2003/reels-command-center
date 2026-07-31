import type { ReactNode } from "react";

import type { SortKey } from "../lib/youtube-metrics";

// K defaults to the YouTube SortKey so every existing call site (which never
// passes K explicitly) keeps its exact prior type — the generic /platforms/*
// pages instantiate VideoTable<Row, PlatformSortKey> instead (see
// components/platform-video-table-section.tsx).
export type VideoTableColumn<T, K = SortKey> = {
  label: string;
  align?: "left" | "right";
  render: (row: T) => ReactNode;
  /** When set, the header becomes clickable and cycles the 3-state sort for this key. */
  sortKey?: K;
};

export function VideoTable<T, K = SortKey>({
  rows,
  columns,
  keyField,
  emptyTitle = "Brak danych",
  emptyMessage = "Brak filmów do wyświetlenia.",
  sort,
  onSortChange,
}: {
  rows: T[];
  columns: VideoTableColumn<T, K>[];
  keyField: (row: T) => string;
  emptyTitle?: string;
  emptyMessage?: string;
  sort?: { key: K; direction: "asc" | "desc" } | null;
  onSortChange?: (key: K) => void;
}) {
  if (rows.length === 0) {
    return (
      <div className="emptyState">
        <h3>{emptyTitle}</h3>
        <p>{emptyMessage}</p>
      </div>
    );
  }
  return (
    <div className="dataTableWrap">
      <table className="dataTable">
        <thead>
          <tr>
            {columns.map((column) => {
              const isSortable = !!column.sortKey && !!onSortChange;
              const isActive = isSortable && sort?.key === column.sortKey;
              const indicator = isActive ? (sort?.direction === "asc" ? "▲" : "▼") : "";
              return (
                <th
                  key={column.label}
                  style={{ textAlign: column.align ?? "left" }}
                  aria-sort={isSortable ? (isActive ? (sort?.direction === "asc" ? "ascending" : "descending") : "none") : undefined}
                >
                  {isSortable ? (
                    <button
                      type="button"
                      className={`sortableHeader${isActive ? " active" : ""}`}
                      onClick={() => onSortChange!(column.sortKey!)}
                    >
                      {column.label} <span className="sortIndicator">{indicator || "↕"}</span>
                    </button>
                  ) : (
                    column.label
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={keyField(row)}>
              {columns.map((column) => (
                <td key={column.label} style={{ textAlign: column.align ?? "left" }}>
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
