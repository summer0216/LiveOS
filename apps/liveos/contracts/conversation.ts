export type MessageFeedback = 'POSITIVE' | 'NEGATIVE';

export interface PresentedMessage {
  id: string;
  /** Server persistence time; absent while this message is still local/streaming. */
  created_at?: string;
  feedback?: MessageFeedback | null;
  role: 'user' | 'assistant';
  content: string;
}
