import { apiFetch } from '@/services/api';
import type { DecisionResult } from '@/services/decision';
import type { LivingProfile } from '@/services/profile';

export type ActionProgressStatus =
  | 'NOT_STARTED'
  | 'PLANNED'
  | 'COMPLETED'
  | 'ABANDONED';

export interface CurrentActionProgress {
  action_id: string | null;
  next_text: string;
  status: ActionProgressStatus | null;
}

export interface LivingDecisionResume {
  conversation_id: string | null;
  profile: LivingProfile | null;
  decision: DecisionResult | null;
  action_progress: CurrentActionProgress | null;
}

export async function getLivingDecisionResume(
  conversationId?: string,
): Promise<LivingDecisionResume> {
  const query = conversationId
    ? `?conversation_id=${encodeURIComponent(conversationId)}`
    : '';
  return apiFetch<LivingDecisionResume>(`/resume${query}`, {
    method: 'GET',
    cache: 'no-store',
  });
}
