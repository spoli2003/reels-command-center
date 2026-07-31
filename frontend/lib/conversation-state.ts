import type { ConversationState } from "./youtube-api";

type ReplyLike = { published_at: string; is_own_reply: boolean };

/**
 * Client-side mirror of comment_intelligence.determine_conversation_state
 * (backend, ADR-019) — used only to give instant feedback after a local reply
 * send/edit/delete without waiting for a refetch. The backend's computation
 * (from the database) is always the source of truth on next load. Takes the
 * minimal ReplyLike shape (not the YouTube-specific ReplyRead) so the generic
 * Facebook/Instagram community components (whose replies have different extra
 * fields) can reuse this unchanged.
 */
export function recomputeConversationState(
  threadPublishedAt: string,
  replies: ReplyLike[],
  wasModerated: boolean,
  topLevelIsOwn = false,
): ConversationState {
  if (wasModerated) return "closed";
  const hasChannelSpoken = topLevelIsOwn || replies.some((reply) => reply.is_own_reply);
  if (!hasChannelSpoken) return "new";
  const messages = [
    { at: threadPublishedAt, isOwn: topLevelIsOwn },
    ...replies.map((reply) => ({ at: reply.published_at, isOwn: reply.is_own_reply })),
  ];
  messages.sort((a, b) => +new Date(a.at) - +new Date(b.at));
  const last = messages[messages.length - 1];
  return last.isOwn ? "resolved" : "waiting";
}
