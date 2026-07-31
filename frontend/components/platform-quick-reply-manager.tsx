"use client";

import { useState } from "react";

import type { PlatformKey, QuickReplyTemplate } from "../lib/platform-api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

/** Same UX/classes as components/quick-reply-manager.tsx, scoped to the given
 * platform's own PlatformAccount (QuickReplyTemplate.account_id needed no
 * schema change to support Facebook/Instagram — see ADR-020). */
export function PlatformQuickReplyManager({
  platform,
  templates,
  onChange,
}: {
  platform: PlatformKey;
  templates: QuickReplyTemplate[];
  onChange: (templates: QuickReplyTemplate[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const [newText, setNewText] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editingText, setEditingText] = useState("");
  const [error, setError] = useState("");

  async function create() {
    const text = newText.trim();
    if (!text) return;
    setError("");
    try {
      const response = await fetch(`${API_URL}/api/platforms/${platform}/quick-replies`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (!response.ok) throw new Error("Nie udało się utworzyć szablonu.");
      const created: QuickReplyTemplate = await response.json();
      onChange([...templates, created]);
      setNewText("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Nie udało się utworzyć szablonu.");
    }
  }

  async function save(id: number) {
    const text = editingText.trim();
    if (!text) return;
    setError("");
    try {
      const response = await fetch(`${API_URL}/api/platforms/${platform}/quick-replies/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (!response.ok) throw new Error("Nie udało się zapisać szablonu.");
      const updated: QuickReplyTemplate = await response.json();
      onChange(templates.map((t) => (t.id === id ? updated : t)));
      setEditingId(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Nie udało się zapisać szablonu.");
    }
  }

  async function remove(id: number) {
    if (!confirm("Usunąć ten szablon odpowiedzi?")) return;
    setError("");
    try {
      const response = await fetch(`${API_URL}/api/platforms/${platform}/quick-replies/${id}`, { method: "DELETE" });
      if (!response.ok && response.status !== 204) throw new Error("Nie udało się usunąć szablonu.");
      onChange(templates.filter((t) => t.id !== id));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Nie udało się usunąć szablonu.");
    }
  }

  if (!open) {
    return (
      <button type="button" className="textLink" onClick={() => setOpen(true)}>
        Zarządzaj szablonami odpowiedzi ({templates.length}) →
      </button>
    );
  }

  return (
    <div className="quickReplyManager">
      <div className="libraryHeading">
        <div>
          <p className="eyebrow">SZABLONY</p>
          <h3>Szablony odpowiedzi</h3>
          <p className="muted">Skonfigurowane tutaj szablony pojawiają się przy każdej odpowiedzi na komentarz.</p>
        </div>
        <button type="button" className="textLink" onClick={() => setOpen(false)}>
          Zwiń
        </button>
      </div>
      {error ? <div className="alert">{error}</div> : null}
      <ul className="quickReplyList">
        {templates.map((template) => (
          <li key={template.id}>
            {editingId === template.id ? (
              <div className="quickReplyEditRow">
                <input value={editingText} onChange={(event) => setEditingText(event.target.value)} />
                <button type="button" className="button" onClick={() => save(template.id)}>
                  Zapisz
                </button>
                <button type="button" className="button secondary" onClick={() => setEditingId(null)}>
                  Anuluj
                </button>
              </div>
            ) : (
              <div className="quickReplyEditRow">
                <span>{template.text}</span>
                <button
                  type="button"
                  className="textLink"
                  onClick={() => {
                    setEditingId(template.id);
                    setEditingText(template.text);
                  }}
                >
                  Edytuj
                </button>
                <button type="button" className="textLink" onClick={() => remove(template.id)}>
                  Usuń
                </button>
              </div>
            )}
          </li>
        ))}
      </ul>
      <div className="quickReplyEditRow">
        <input value={newText} onChange={(event) => setNewText(event.target.value)} placeholder="Nowy szablon odpowiedzi…" />
        <button type="button" className="button" onClick={create} disabled={!newText.trim()}>
          Dodaj
        </button>
      </div>
    </div>
  );
}
