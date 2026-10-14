import type { PresentedMessage } from '../contracts/conversation';

interface HistoryMessage {
  role: 'user' | 'assistant';
  content: string;
}

export function restoreConversationMessages(conversationId: string, history: readonly HistoryMessage[]): PresentedMessage[] {
  return history.map((message, index) => ({
    id: `${conversationId}:${index}`,
    role: message.role,
    content: message.content,
  }));
}

export function appendAssistantChunk(
  messages: readonly PresentedMessage[],
  assistantMessageId: string,
  chunk: string,
): PresentedMessage[] {
  return messages.map((message) => message.id === assistantMessageId && message.role === 'assistant'
    ? { ...message, content: message.content + chunk }
    : message);
}
