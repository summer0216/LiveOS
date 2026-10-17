import type { PresentedMessage } from '../contracts/conversation';
import type { ConversationHistory } from '../infrastructure/conversationApi';

export function restoreConversationMessages(history: ConversationHistory['messages']): PresentedMessage[] {
  return history.map((message) => ({
    id: message.id,
    created_at: message.created_at,
    ...(message.feedback !== undefined ? { feedback: message.feedback } : {}),
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
