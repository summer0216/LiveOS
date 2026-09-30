import { apiRequest } from '@/services/api';

export interface PossibleLifeWorldState {
  id: string;
  work_subject_owner_id: string;
  residence_property_id: string;
  living_time_residence_property_id: string;
  personal_meaning_reference: string;
  work_subject: {
    identity: string;
    geographic_identity: string;
    geographic_precision: 'PLACE';
    geographic_status: 'GROUNDED';
    lng: number;
    lat: number;
    relationship: 'WORK';
  };
  living_time: {
    residence_property_id: string;
    residence_identity: string;
    residence_geographic_identity: string;
    work_subject_identity: string;
    work_geographic_identity: string;
    travel_minutes: number;
    travel_mode: 'WALKING' | 'PUBLIC_TRANSIT';
    evidence_source: string;
    evidence_reference: string;
  };
  personal_meaning: {
    reference: string;
    maximum_commute_minutes: number;
    satisfied: boolean;
  };
}

export async function getPossibleLives(
  conversationId: string,
  signal?: AbortSignal,
): Promise<PossibleLifeWorldState[]> {
  const response = await apiRequest(
    `/possible-lives?conversation_id=${encodeURIComponent(conversationId)}`,
    { method: 'GET', cache: 'no-store', signal },
  );
  if (!response.ok) {
    throw new Error(`Failed to fetch Possible Lives: ${response.status}`);
  }
  const data = (await response.json()) as { items: PossibleLifeWorldState[] };
  return data.items;
}
