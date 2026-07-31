"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { AppShell } from "../../../../components/app-shell";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

type PendingInstagram = {
  id: string;
  username: string | null;
  picture_url: string | null;
  account_type: string | null;
  followers: number | null;
  media_count: number | null;
};
type PendingPage = {
  id: string;
  name: string;
  category: string | null;
  picture_url: string | null;
  followers: number | null;
  instagram: PendingInstagram | null;
};
type PendingPagesResponse = { target: "facebook" | "instagram"; pages: PendingPage[] };

function compact(value: number) {
  return new Intl.NumberFormat("pl-PL", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

/** Release 0.8.1 (ADR-023) — RCC never auto-connects the first Facebook Page a
 * Meta account manages. This screen lands right after OAuth consent (redirected
 * here by GET /api/platforms/meta/callback with a `selection` id) and lets the
 * user pick explicitly, with enough context per Page (picture, category,
 * followers, linked Instagram) to choose correctly. */
export default function SelectMetaPagePage() {
  return (
    <AppShell active="/platforms">
      <Suspense fallback={<div className="emptyState"><h3>Wczytuję…</h3></div>}>
        <SelectMetaPageContent />
      </Suspense>
    </AppShell>
  );
}

function SelectMetaPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const selectionId = searchParams.get("selection") ?? "";

  const [data, setData] = useState<PendingPagesResponse | null>(null);
  const [loadError, setLoadError] = useState("");
  const [selectingId, setSelectingId] = useState<string | null>(null);
  const [selectError, setSelectError] = useState("");

  useEffect(() => {
    if (!selectionId) {
      setLoadError("Brak identyfikatora sesji wyboru — połącz się ponownie z /platforms/facebook lub /platforms/instagram.");
      return;
    }
    (async () => {
      try {
        const response = await fetch(`${API_URL}/api/platforms/meta/pending-pages?selection=${encodeURIComponent(selectionId)}`, {
          cache: "no-store",
        });
        const body = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(body.detail ?? "Nie udało się wczytać listy Stron.");
        setData(body as PendingPagesResponse);
      } catch (caught) {
        setLoadError(caught instanceof Error ? caught.message : "Nie udało się wczytać listy Stron.");
      }
    })();
  }, [selectionId]);

  async function selectPage(pageId: string) {
    setSelectingId(pageId);
    setSelectError("");
    try {
      const response = await fetch(`${API_URL}/api/platforms/meta/select-page`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ selection_id: selectionId, page_id: pageId }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail ?? "Nie udało się połączyć wybranej Strony.");
      const query = new URLSearchParams({ connected: "1", sync: body.initial_sync_status ?? "not_started" });
      if (typeof body.imported_items === "number") query.set("imported", String(body.imported_items));
      if (typeof body.comments_imported === "number") query.set("comments", String(body.comments_imported));
      if (body.initial_sync_message) query.set("message", body.initial_sync_message);
      router.push(`/platforms/${body.platform}?${query.toString()}`);
    } catch (caught) {
      setSelectError(caught instanceof Error ? caught.message : "Nie udało się połączyć wybranej Strony.");
      setSelectingId(null);
    }
  }

  const targetLabel = data?.target === "instagram" ? "Instagram" : "Facebook";

  return (
    <>
      <header className="topbar">
        <div>
          <p className="eyebrow">POŁĄCZ META</p>
          <h1>Wybierz Stronę</h1>
          <p className="muted">
            {data
              ? `Twoje konto Meta zarządza ${data.pages.length} ${data.pages.length === 1 ? "Stroną" : "Stronami"}. Wybierz, którą połączyć z ${targetLabel}.`
              : "Wczytuję Strony powiązane z Twoim kontem Meta…"}
          </p>
        </div>
      </header>

      {loadError && <div className="alert">{loadError}</div>}
      {selectError && !loadError ? <div className="alert">{selectError}</div> : null}

      {!data && !loadError ? (
        <div className="emptyState">
          <h3>Wczytuję…</h3>
        </div>
      ) : data && data.pages.length === 0 ? (
        <div className="emptyState">
          <h3>Brak Stron</h3>
          <p>To konto Meta nie zarządza żadną Stroną na Facebooku.</p>
        </div>
      ) : data ? (
        <section className="libraryPanel">
          <div className="pageSelectionList">
            {data.pages.map((page) => {
              const disabledForInstagram = data.target === "instagram" && page.instagram === null;
              return (
                <div key={page.id} className="pageSelectionCard">
                  {page.picture_url ? (
                    <img className="pageSelectionAvatar" src={page.picture_url} alt="" />
                  ) : (
                    <div className="pageSelectionAvatarPlaceholder">{page.name.slice(0, 1).toUpperCase()}</div>
                  )}
                  <div className="pageSelectionInfo">
                    <strong>{page.name}</strong>
                    <p className="pageSelectionMeta">
                      {page.category ?? "Strona na Facebooku"}
                      {page.followers !== null ? ` · ${compact(page.followers)} obserwujących` : ""}
                    </p>
                    {data.target === "instagram" ? (
                      <div className="pageSelectionInstagramRow">
                        {page.instagram ? (
                          <>
                            {page.instagram.picture_url ? (
                              <img className="pageSelectionInstagramAvatar" src={page.instagram.picture_url} alt="" />
                            ) : null}
                            <span className="pageSelectionInstagramBadge">
                              ◎ Instagram: @{page.instagram.username ?? "połączony"}
                            </span>
                            {page.instagram.account_type ? (
                              <span className="muted">{page.instagram.account_type === "CREATOR" ? "Creator" : "Business"}</span>
                            ) : null}
                          </>
                        ) : (
                          <span className="pageSelectionInstagramMissing">Brak połączonego konta Instagram Professional</span>
                        )}
                      </div>
                    ) : null}
                  </div>
                  <button
                    type="button"
                    className={`button ${disabledForInstagram ? "disabled" : ""}`}
                    disabled={selectingId !== null || disabledForInstagram}
                    title={disabledForInstagram ? "Ta Strona nie ma podłączonego konta Instagram Professional." : undefined}
                    onClick={() => selectPage(page.id)}
                  >
                    {selectingId === page.id ? "Łączę…" : `Połącz ${data.target === "instagram" ? "Instagram" : "Stronę"}`}
                  </button>
                </div>
              );
            })}
          </div>
        </section>
      ) : null}
    </>
  );
}
