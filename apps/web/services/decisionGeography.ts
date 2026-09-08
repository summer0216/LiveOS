import { apiRequest } from '@/services/api';

export interface DecisionGeography {
  conversation_id: string;
  intent_established: boolean;
  intent_type: string | null;
  identity: string;
  status: 'UNRESOLVED' | 'GROUNDED';
  lng: number | null;
  lat: number | null;
}

export async function getDecisionGeography(
  conversationId: string,
): Promise<DecisionGeography | null> {
  const response = await apiRequest(
    `/decision-geography?conversation_id=${encodeURIComponent(conversationId)}`,
    { method: 'GET', cache: 'no-store' },
  );

  if (response.status === 404) return null;
  if (!response.ok) {
    throw new Error(`Failed to fetch decision geography: ${response.status}`);
  }
  return response.json() as Promise<DecisionGeography | null>;
}
