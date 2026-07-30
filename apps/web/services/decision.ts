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

export interface DecisionRecord {
  id: string;
  conversation_id: string;
  created_at: string;
  summary: string;
  best_property_id: string;
  reasons: DecisionReason[];
  trade_offs: DecisionTradeOff[];
  confidence: number | null;
}

export interface DecisionHistoryResponse {
  conversation_id: string;
  items: DecisionRecord[];
  total: number;
}

function isDecisionItem(value: unknown): value is DecisionReason {
  if (typeof value !== 'object' || value === null) {
    return false;
  }

  const item = value as Record<string, unknown>;

  return (
    typeof item.title === 'string' &&
    typeof item.description === 'string'
  );
}

function isDecisionRecord(value: unknown): value is DecisionRecord {
  if (typeof value !== 'object' || value === null) {
    return false;
  }

  const record = value as Record<string, unknown>;

  return (
    typeof record.id === 'string' &&
    typeof record.conversation_id === 'string' &&
    typeof record.created_at === 'string' &&
    typeof record.summary === 'string' &&
    typeof record.best_property_id === 'string' &&
    Array.isArray(record.reasons) &&
    record.reasons.every(isDecisionItem) &&
    Array.isArray(record.trade_offs) &&
    record.trade_offs.every(isDecisionItem) &&
    (typeof record.confidence === 'number' || record.confidence === null)
  );
}

function isDecisionHistoryResponse(
  value: unknown,
): value is DecisionHistoryResponse {
  if (typeof value !== 'object' || value === null) {
    return false;
  }

  const response = value as Record<string, unknown>;

  return (
    typeof response.conversation_id === 'string' &&
    Array.isArray(response.items) &&
    response.items.every(isDecisionRecord) &&
    typeof response.total === 'number' &&
    Number.isInteger(response.total) &&
    response.total >= 0
  );
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

export async function getDecisionHistory(
  conversationId: string,
  signal?: AbortSignal,
): Promise<DecisionHistoryResponse> {
  const response = await apiFetch<unknown>(
    `/conversations/${encodeURIComponent(conversationId)}/decisions/history`,
    {
      method: 'GET',
      cache: 'no-store',
      signal,
    },
  );

  if (!isDecisionHistoryResponse(response)) {
    throw new Error('Invalid Decision History response.');
  }

  if (response.conversation_id !== conversationId) {
    throw new Error('Decision History conversation mismatch.');
  }

  return response;
}
