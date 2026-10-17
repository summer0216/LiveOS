import { getConversationHistory as readHistory } from '@/services/chat';
import type { ConversationHistory as RuntimeHistory } from '@/services/chat';
import { apiFetch } from '@/services/api';
import type { MessageFeedback } from '../contracts/conversation';

export { streamMessage } from '@/services/chat';
export type ConversationHistory = Omit<RuntimeHistory, 'messages'> & {
  messages: Array<RuntimeHistory['messages'][number] & { feedback?: MessageFeedback | null }>;
};

export async function getConversationHistory(conversationId: string): Promise<ConversationHistory> {
  return readHistory(conversationId);
}

export function setMessageFeedback(conversationId: string, messageId: string, feedback: MessageFeedback | null) {
  return apiFetch<{ message_id: string; feedback: MessageFeedback | null }>(
    `/conversations/${encodeURIComponent(conversationId)}/messages/${encodeURIComponent(messageId)}/feedback`,
    { method: 'PUT', body: JSON.stringify({ feedback }) },
  );
}
