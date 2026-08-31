import { apiFetch } from '@/services/api';
import type { DecisionResult } from '@/services/decision';
import type { LivingProfile } from '@/services/profile';

export type ActionProgressStatus =
  | 'NOT_STARTED'
  | 'PLANNED'
  | 'COMPLETED'
  | 'ABANDONED';

export type VerificationOutcomeStatus =
  | 'CONFIRMED'
  | 'DISCONFIRMED'
  | 'INCONCLUSIVE';

export interface VerificationEvidence {
  field: 'city' | 'commute_minutes' | 'rent' | 'statement';
  value: number | string;
  statement: string;
  provenance: 'USER_REPORTED';
}

export interface CurrentActionProgress {
  action_id: string | null;
  next_text: string;
  status: ActionProgressStatus | null;
  outcome_status: VerificationOutcomeStatus | null;
  verification_evidence: VerificationEvidence[];
}

export interface LatestVerifiedAction {
  action_id: string;
  next_text: string;
  status: 'COMPLETED';
  outcome_status: VerificationOutcomeStatus;
  verification_evidence: VerificationEvidence[];
}

export interface LivingDecisionResume {
  conversation_id: string | null;
  profile: LivingProfile | null;
  decision: DecisionResult | null;
  action_progress: CurrentActionProgress | null;
  latest_verified_action: LatestVerifiedAction | null;
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
