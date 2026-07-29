import type { ReactNode } from "react";

import type { SortKey, TableSort } from "../lib/youtube-metrics";

export type VideoTableColumn<T> = {
  label: string;
  align?: "left" | "right";
  render: (row: T) => ReactNode;
  /** When set, the header becomes clickable and cycles the 3-state sort for this key. */
  sortKey?: SortKey;
};

export function VideoTable<T>({
  rows,
  columns,
  keyField,
  emptyTitle = "Brak danych",
  emptyMessage = "Brak filmów do wyświetlenia.",
  sort,
  onSortChange,
}: {
  rows: T[];
  columns: VideoTableColumn<T>[];
  keyField: (row: T) => string;
  emptyTitle?: string;
  emptyMessage?: string;
  sort?: TableSort;
  onSortChange?: (key: SortKey) => void;
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
                <th key={column.label} style={{ textAlign: column.align ?? "left" }}>
                  {isSortable ? (
                    <button
                      type="button"
                      className={`sortableHeader${isActive ? " active" : ""}`}
                      onClick={() => onSortChange!(column.sortKey!)}
                      aria-sort={isActive ? (sort?.direction === "asc" ? "ascending" : "descending") : "none"}
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
