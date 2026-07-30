import { apiFetch } from '@/services/api';

export interface DecisionReason {
  title: string;
  description: string;
}

export interface DecisionTradeOff {
  title: string;
  description: string;
}

export interface DecisionResult {
  status: 'waiting' | 'ready';
  summary: string | null;
  best_property_id: string | null;
  reasons: DecisionReason[];
  trade_offs: DecisionTradeOff[];
  confidence: number | null;
}

export async function getDecision(
  conversationId: string,
): Promise<DecisionResult> {
  return apiFetch<DecisionResult>(
    `/decisions?conversation_id=${encodeURIComponent(conversationId)}`,
    {
      method: 'GET',
      cache: 'no-store',
    },
  );
}
