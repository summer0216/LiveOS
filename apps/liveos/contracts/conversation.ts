export interface PresentedMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}
