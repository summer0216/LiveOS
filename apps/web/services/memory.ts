import { apiFetch } from '@/services/api';

export type DecisionMemoryCategory =
  | 'priority'
  | 'preference'
  | 'constraint'
  | 'trade_off';

export interface DecisionMemory {
  id: string;
  conversation_id: string;
  category: DecisionMemoryCategory;
  content: string;
  confidence: number;
  evidence_record_ids: string[];
  evidence_count: number;
  created_at: string;
  updated_at: string;
}

export interface DecisionMemoryListResponse {
  conversation_id: string;
  memories: DecisionMemory[];
}

export type DecisionMemoryExtractionStatus =
  | 'completed'
  | 'insufficient_history'
  | 'failed';

export interface DecisionMemoryRefreshResponse {
  conversation_id: string;
  status: DecisionMemoryExtractionStatus;
  history_record_count: number;
  candidate_count: number;
  saved_count: number;
  rejected_count: number;
  memories: DecisionMemory[];
}

export async function getDecisionMemories(
  conversationId: string,
  signal?: AbortSignal,
): Promise<DecisionMemoryListResponse> {
  return apiFetch<DecisionMemoryListResponse>(
    `/memories?conversation_id=${encodeURIComponent(conversationId)}`,
    {
      method: 'GET',
      cache: 'no-store',
      signal,
    },
  );
}

export async function refreshDecisionMemories(
  conversationId: string,
): Promise<DecisionMemoryRefreshResponse> {
  return apiFetch<DecisionMemoryRefreshResponse>(
    `/memories/refresh?conversation_id=${encodeURIComponent(conversationId)}`,
    {
      method: 'POST',
      cache: 'no-store',
    },
  );
}
