import type { ConversationState } from "../lib/youtube-api";

/** Mirrors backend CONVERSATION_STATE_META (comment_intelligence.py) exactly —
 * one place, same emoji/text/tone everywhere a conversation state is shown. */
export const CONVERSATION_STATE_META: Record<ConversationState, { emoji: string; text: string; tone: string }> = {
  resolved: { emoji: "🟢", text: "Rozwiązane", tone: "great" },
  waiting: { emoji: "🟡", text: "Czeka na odpowiedź", tone: "weak" },
  new: { emoji: "🔵", text: "Nowy", tone: "good" },
  closed: { emoji: "⚪", text: "Zamknięty", tone: "average" },
};

export function ConversationStateBadge({ state }: { state: ConversationState }) {
  const meta = CONVERSATION_STATE_META[state];
  return (
    <span
      className={`performanceBadge ${meta.tone}`}
      title="Stan rozmowy: ustalany na podstawie ostatniej wiadomości w całym wątku, nie samego komentarza głównego."
    >
      {meta.emoji} {meta.text}
    </span>
  );
}
