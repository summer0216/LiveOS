export interface ChatRequest {
  conversation_id: string;
  message: string;
  clarification_target?: 'WORK_LOCATION';
  current_geographic_reality?: {
    lng: number;
    lat: number;
  };
}

export interface ChatResponse {
  reply: string;
}
