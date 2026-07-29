"use client";

import {
  DATE_RANGE_OPTIONS,
  QUICK_FILTER_OPTIONS,
  SORT_OPTIONS,
  type DateRangeKey,
  type QuickFilter,
  type SortDirection,
  type SortKey,
} from "../lib/youtube-metrics";

export function DashboardFilterBar({
  dateRange,
  onDateRangeChange,
  search,
  onSearchChange,
  sortKey,
  sortDirection,
  onSortChange,
  minViews,
  onMinViewsChange,
  maxViews,
  onMaxViewsChange,
  quickFilter,
  onQuickFilterChange,
  resultCount,
  activeLabel,
}: {
  dateRange: DateRangeKey;
  onDateRangeChange: (value: DateRangeKey) => void;
  search: string;
  onSearchChange: (value: string) => void;
  sortKey: SortKey;
  sortDirection: SortDirection;
  onSortChange: (key: SortKey, direction: SortDirection) => void;
  minViews?: number | null;
  onMinViewsChange?: (value: number | null) => void;
  maxViews?: number | null;
  onMaxViewsChange?: (value: number | null) => void;
  quickFilter?: QuickFilter;
  onQuickFilterChange?: (value: QuickFilter) => void;
  resultCount: number;
  activeLabel: string;
}) {
  const showViewsRange = onMinViewsChange && onMaxViewsChange;
  const showQuickFilter = onQuickFilterChange;

  return (
    <div className="filterBar">
      <div className="filterBarRow">
        <select value={dateRange} onChange={(event) => onDateRangeChange(event.target.value as DateRangeKey)} aria-label="Zakres dat">
          {DATE_RANGE_OPTIONS.map((option) => (
            <option key={option.key} value={option.key}>
              {option.label}
            </option>
          ))}
        </select>
        <input
          className="searchInput"
          placeholder="Szukaj filmu po tytule…"
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          aria-label="Szukaj filmu po tytule"
        />
        <select
          value={sortKey}
          onChange={(event) => onSortChange(event.target.value as SortKey, sortDirection)}
          aria-label="Sortowanie listy „Wszystkie filmy”"
        >
          {SORT_OPTIONS.map((option) => (
            <option key={option.key} value={option.key}>
              Sortuj: {option.label}
            </option>
          ))}
        </select>
        <select
          value={sortDirection}
          onChange={(event) => onSortChange(sortKey, event.target.value as SortDirection)}
          aria-label="Kierunek sortowania"
        >
          <option value="desc">Malejąco</option>
          <option value="asc">Rosnąco</option>
        </select>
      </div>
      {showViewsRange ? (
        <div className="filterBarRow">
          <input
            type="number"
            min={0}
            placeholder="Min. wyświetleń"
            value={minViews ?? ""}
            onChange={(event) => onMinViewsChange!(event.target.value ? Number(event.target.value) : null)}
            aria-label="Minimalna liczba wyświetleń"
            className="viewsRangeInput"
          />
          <input
            type="number"
            min={0}
            placeholder="Maks. wyświetleń"
            value={maxViews ?? ""}
            onChange={(event) => onMaxViewsChange!(event.target.value ? Number(event.target.value) : null)}
            aria-label="Maksymalna liczba wyświetleń"
            className="viewsRangeInput"
          />
          {showQuickFilter ? (
            <div className="quickFilterGroup" role="group" aria-label="Szybki filtr">
              {QUICK_FILTER_OPTIONS.map((option) => (
                <button
                  key={option.key}
                  type="button"
                  className={`quickFilterButton${quickFilter === option.key ? " active" : ""}`}
                  onClick={() => onQuickFilterChange!(option.key)}
                >
                  {option.label}
                </button>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
      <p className="filterBarActive">
        Aktywny zakres: <strong>{activeLabel}</strong> · {resultCount} {resultCount === 1 ? "film" : "filmów"}
      </p>
    </div>
  );
}
