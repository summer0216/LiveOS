export interface ChatRequest {
  conversation_id: string;
  message: string;
}

export interface ChatResponse {
  reply: string;
}