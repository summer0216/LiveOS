import { apiFetch } from '@/services/api';
import type { DecisionResult } from '@/services/decision';
import type { LivingProfile } from '@/services/profile';

export interface LivingDecisionResume {
  conversation_id: string | null;
  profile: LivingProfile | null;
  decision: DecisionResult | null;
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
