import type { ConversationState, ReplyRead } from "./youtube-api";

/**
 * Client-side mirror of comment_intelligence.determine_conversation_state
 * (backend, ADR-019) — used only to give instant feedback after a local reply
 * send/edit/delete without waiting for a refetch. The backend's computation
 * (from the database) is always the source of truth on next load.
 */
export function recomputeConversationState(
  threadPublishedAt: string,
  replies: ReplyRead[],
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
