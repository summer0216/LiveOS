export interface ChatRequest {
  conversation_id: string;
  message: string;
  clarification_target?: 'WORK_LOCATION';
  rent_property_id?: string;
  user_reality_property_id?: string;
  user_decision_property_id?: string;
  current_geographic_reality?: {
    lng: number;
    lat: number;
  };
}

export interface ChatResponse {
  reply: string;
}
