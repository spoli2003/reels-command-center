"use client";

import Link from "next/link";
import { useState } from "react";

import { ReplyComposer } from "./reply-composer";
import type { CommentThreadRead, QuickReplyTemplate, ReplyRead } from "../lib/youtube-api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

function formatDate(value: string) {
  return new Intl.DateTimeFormat("pl-PL", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(
    new Date(value),
  );
}

function youtubeCommentUrl(videoId: string, commentId: string) {
  return `https://www.youtube.com/watch?v=${videoId}&lc=${commentId}`;
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
  const [answered, setAnswered] = useState(row.is_answered);

  return (
    <article className="commentCard">
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
          {row.is_likely_question ? <span className="performanceBadge good" title="Wykryte na podstawie znaku zapytania lub słów pytających">Prawdopodobne pytanie</span> : null}
          <span className={`performanceBadge ${answered ? "great" : "weak"}`}>{answered ? "Odpowiedziano" : "Bez odpowiedzi"}</span>
        </div>
      </div>

      <p className="commentText">{row.text_original}</p>

      <div className="commentMetaRow">
        <span title="Polubienia komentarza">👍 {row.like_count.toLocaleString("pl-PL")}</span>
        <span title="Liczba odpowiedzi w wątku">💬 {row.total_reply_count.toLocaleString("pl-PL")}</span>
        <a href={youtubeCommentUrl(row.youtube_video_id, row.top_level_comment_id)} target="_blank" rel="noreferrer" className="textLink">
          Otwórz na YouTube →
        </a>
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
                  onChanged={(updated) => setReplies((current) => current.map((r) => (r.platform_comment_id === updated.platform_comment_id ? updated : r)))}
                  onDeleted={() => {
                    setReplies((current) => {
                      const next = current.filter((r) => r.platform_comment_id !== reply.platform_comment_id);
                      setAnswered(next.some((r) => r.is_own_reply));
                      return next;
                    });
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
            setReplies((current) => [...current, reply]);
            setAnswered(true);
          }}
        />
      ) : (
        <p className="muted">Ten wątek nie zezwala na odpowiedzi.</p>
      )}
    </article>
  );
}
