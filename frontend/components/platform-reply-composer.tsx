"use client";

import { useState } from "react";

import type { PlatformKey, PlatformReply, QuickReplyTemplate } from "../lib/platform-api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
const MAX_LENGTH = 10000;

type ComposerState = "idle" | "sending" | "success" | "error";

/** Same UX/classes as components/reply-composer.tsx, posting to the generic
 * /api/platforms/{platform}/comments/... endpoints instead of YouTube's. */
export function PlatformReplyComposer({
  platform,
  threadPlatformId,
  quickReplies,
  onSent,
}: {
  platform: PlatformKey;
  threadPlatformId: string;
  quickReplies: QuickReplyTemplate[];
  onSent: (reply: PlatformReply) => void;
}) {
  const [text, setText] = useState("");
  const [state, setState] = useState<ComposerState>("idle");
  const [error, setError] = useState("");
  const [open, setOpen] = useState(false);

  async function send() {
    const trimmed = text.trim();
    if (!trimmed || state === "sending") return;
    setState("sending");
    setError("");
    try {
      const response = await fetch(`${API_URL}/api/platforms/${platform}/comments/threads/${threadPlatformId}/reply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: trimmed }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail ?? "Nie udało się opublikować odpowiedzi.");
      }
      const reply: PlatformReply = await response.json();
      setState("success");
      setText("");
      onSent(reply);
    } catch (caught) {
      setState("error");
      setError(caught instanceof Error ? caught.message : "Nie udało się opublikować odpowiedzi.");
    }
  }

  if (!open) {
    return (
      <button type="button" className="button secondary replyToggle" onClick={() => setOpen(true)}>
        Odpowiedz
      </button>
    );
  }

  return (
    <div className="replyComposer">
      <textarea
        value={text}
        onChange={(event) => {
          setText(event.target.value.slice(0, MAX_LENGTH));
          if (state === "error") setState("idle");
        }}
        placeholder="Napisz odpowiedź…"
        rows={3}
        disabled={state === "sending"}
        maxLength={MAX_LENGTH}
      />
      {quickReplies.length > 0 ? (
        <div className="quickReplyPickerRow">
          <span className="muted">Szablony:</span>
          {quickReplies.map((template) => (
            <button
              key={template.id}
              type="button"
              className="quickFilterButton"
              onClick={() => setText(template.text)}
              disabled={state === "sending"}
              title="Wstawia treść szablonu do pola odpowiedzi — nie wysyła automatycznie"
            >
              {template.text.length > 24 ? `${template.text.slice(0, 23)}…` : template.text}
            </button>
          ))}
        </div>
      ) : null}
      <div className="replyComposerFooter">
        <span className="charCounter">
          {text.length}/{MAX_LENGTH}
        </span>
        <div className="replyComposerActions">
          <button
            type="button"
            className="button secondary"
            onClick={() => {
              setOpen(false);
              setState("idle");
              setError("");
            }}
            disabled={state === "sending"}
          >
            Anuluj
          </button>
          <button type="button" className="button" onClick={send} disabled={state === "sending" || !text.trim()}>
            {state === "sending" ? "Wysyłanie…" : "Wyślij"}
          </button>
        </div>
      </div>
      {state === "error" ? <div className="alert">{error}</div> : null}
    </div>
  );
}
