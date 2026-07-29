"use client";

import Link from "next/link";
import { useState } from "react";

import { ConversationStateBadge } from "./conversation-state-badge";
import { ReplyComposer } from "./reply-composer";
import { recomputeConversationState } from "../lib/conversation-state";
import type { CommentThreadRead, QuickReplyTemplate, ReplyRead } from "../lib/youtube-api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
const PRIORITY_HIGH_THRESHOLD = 60;

function formatDate(value: string) {
  return new Intl.DateTimeFormat("pl-PL", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(
    new Date(value),
  );
}

function youtubeCommentUrl(videoId: string, commentId: string) {
  return `https://www.youtube.com/watch?v=${videoId}&lc=${commentId}`;
}

function ViewerRatingBadge({ rating }: { rating: string | null }) {
  if (rating !== "like") return null;
  return (
    <span
      className="performanceBadge good"
      title="Właściciel kanału polubił ten komentarz na YouTube. Odczyt z API — RCC nie generuje polubień."
    >
      👍 Polubione przez kanał
    </span>
  );
}

function EditableOwnReply({ reply, onChanged, onDeleted }: { reply: ReplyRead; onChanged: (reply: ReplyRead) => void; onDeleted: () => void }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(reply.text_original);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function save() {
    const trimmed = text.trim();
    if (!trimmed) return;
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${API_URL}/api/integrations/youtube/comments/${reply.platform_comment_id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: trimmed }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail ?? "Nie udało się zapisać zmiany.");
      }
      const updated: ReplyRead = await response.json();
      onChanged(updated);
      setEditing(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Nie udało się zapisać zmiany.");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!confirm("Usunąć tę odpowiedź z YouTube i z RCC? Tej operacji nie można cofnąć.")) return;
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${API_URL}/api/integrations/youtube/comments/${reply.platform_comment_id}`, { method: "DELETE" });
      if (!response.ok && response.status !== 204) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail ?? "Nie udało się usunąć odpowiedzi.");
      }
      onDeleted();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Nie udało się usunąć odpowiedzi.");
      setBusy(false);
    }
  }

  if (editing) {
    return (
      <div className="replyComposer ownReplyEdit">
        <textarea value={text} onChange={(event) => setText(event.target.value)} rows={2} disabled={busy} />
        <div className="replyComposerFooter">
          <span />
          <div className="replyComposerActions">
            <button type="button" className="button secondary" onClick={() => setEditing(false)} disabled={busy}>
              Anuluj
            </button>
            <button type="button" className="button" onClick={save} disabled={busy || !text.trim()}>
              {busy ? "Zapisywanie…" : "Zapisz"}
            </button>
          </div>
        </div>
        {error ? <div className="alert">{error}</div> : null}
      </div>
    );
  }

  return (
    <div className="ownReplyActions">
      <button type="button" className="textLink" onClick={() => setEditing(true)}>
        Edytuj
      </button>
      <button type="button" className="textLink" onClick={remove} disabled={busy}>
        {busy ? "Usuwanie…" : "Usuń"}
      </button>
      {error ? <div className="alert">{error}</div> : null}
    </div>
  );
}

export function CommentThreadCard({
  row,
  quickReplies,
  showVideo = true,
}: {
  row: CommentThreadRead;
  quickReplies: QuickReplyTemplate[];
  showVideo?: boolean;
}) {
  const [replies, setReplies] = useState(row.replies);
  const [state, setState] = useState(row.conversation_state);
  const isModerated = row.conversation_state === "closed";
  // The top-level comment's own authorship never changes across local reply
  // mutations — infer it once from the server-computed initial state (a
  // channel's own pinned top-level comment with zero replies is "resolved").
  const topLevelIsOwn = row.replies.length === 0 && row.conversation_state === "resolved";

  function refreshState(nextReplies: ReplyRead[]) {
    setState(recomputeConversationState(row.published_at, nextReplies, isModerated, topLevelIsOwn));
  }

  return (
    <article className={`commentCard${row.is_highly_liked ? " highlyLiked" : ""}`}>
      <div className="commentCardHeader">
        {row.author_avatar_url ? (
          <img className="commentAvatar" src={row.author_avatar_url} alt="" />
        ) : (
          <div className="commentAvatar placeholder">{row.author_display_name.slice(0, 1).toUpperCase()}</div>
        )}
        <div className="commentAuthorBlock">
          <strong>{row.author_display_name}</strong>
          <span className="muted">{formatDate(row.published_at)}</span>
        </div>
        <div className="commentCardBadges">
          {row.is_likely_question ? (
            <span className="performanceBadge good" title="Wykryte na podstawie znaku zapytania lub słów pytających — nie mamy pewności, to sygnał, nie fakt.">
              Prawdopodobne pytanie
            </span>
          ) : null}
          {row.priority_score >= PRIORITY_HIGH_THRESHOLD ? (
            <span
              className="performanceBadge weak"
              title={`Priorytet ${Math.round(row.priority_score)}/100 — liczony z: czy to pytanie, jak niedawno była ostatnia wiadomość, liczby polubień i odpowiedzi. Rozwiązane rozmowy zawsze mają priorytet 0.`}
            >
              ⚠ Wysoki priorytet
            </span>
          ) : null}
          <ConversationStateBadge state={state} />
        </div>
      </div>

      <p className="commentText">{row.text_original}</p>

      <div className="commentMetaRow">
        <span title="Polubienia komentarza (dane z YouTube — sortowanie i wyróżnienie dostępne, bez przycisku Lubię to)">
          👍 {row.like_count.toLocaleString("pl-PL")}
        </span>
        <span title="Liczba odpowiedzi w wątku">💬 {row.total_reply_count.toLocaleString("pl-PL")}</span>
        <ViewerRatingBadge rating={row.viewer_rating} />
        <a href={youtubeCommentUrl(row.youtube_video_id, row.top_level_comment_id)} target="_blank" rel="noreferrer" className="textLink">
          Otwórz na YouTube →
        </a>
        {showVideo ? (
          <Link href={`/youtube/videos/${row.youtube_video_id}`} className="textLink">
            Analityka filmu →
          </Link>
        ) : null}
      </div>

      {showVideo ? (
        <Link href={`/youtube/videos/${row.youtube_video_id}`} className="commentVideoRef">
          {row.video_thumbnail_url ? <img src={row.video_thumbnail_url} alt="" /> : <div className="commentVideoRefThumb placeholder" />}
          <span>{row.video_title}</span>
        </Link>
      ) : null}

      {replies.length > 0 ? (
        <div className="commentReplies">
          {replies.map((reply) => (
            <div key={reply.platform_comment_id} className={`commentReply${reply.is_own_reply ? " own" : ""}`}>
              <div className="commentReplyHeader">
                <strong>{reply.author_display_name}</strong>
                {reply.is_own_reply ? <span className="pill success">Odpowiedź kanału</span> : null}
                <span className="muted">{formatDate(reply.published_at)}</span>
              </div>
              <p>{reply.text_original}</p>
              {reply.is_own_reply ? (
                <EditableOwnReply
                  reply={reply}
                  onChanged={(updated) => {
                    const next = replies.map((r) => (r.platform_comment_id === updated.platform_comment_id ? updated : r));
                    setReplies(next);
                    refreshState(next);
                  }}
                  onDeleted={() => {
                    const next = replies.filter((r) => r.platform_comment_id !== reply.platform_comment_id);
                    setReplies(next);
                    refreshState(next);
                  }}
                />
              ) : null}
            </div>
          ))}
        </div>
      ) : null}

      {row.can_reply ? (
        <ReplyComposer
          threadPlatformId={row.platform_thread_id}
          quickReplies={quickReplies}
          onSent={(reply) => {
            const next = [...replies, reply];
            setReplies(next);
            refreshState(next);
          }}
        />
      ) : (
        <p className="muted">Ten wątek nie zezwala na odpowiedzi.</p>
      )}
    </article>
  );
}
