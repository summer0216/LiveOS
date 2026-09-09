export interface ChatRequest {
  conversation_id: string;
  message: string;
  current_geographic_reality?: {
    lng: number;
    lat: number;
  };
}

export interface ChatResponse {
  reply: string;
}
