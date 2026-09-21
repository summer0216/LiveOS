import { apiRequest } from '@/services/api';

export interface Property {
  id: string;
  conversation_id: string;
  provenance?: 'USER_PROVIDED' | 'AMAP_RESIDENTIAL_POI';
  external_id?: string | null;
  title: string | null;
  district: string | null;
  rent: number | null;
  rent_source: 'USER_CONFIRMED_REALITY' | 'USER_PROVIDED' | 'EXTERNAL_SOURCE' | null;
  rent_source_reference: string | null;
  rent_observed_at: string | null;
  independent_kitchen: boolean | null;
  independent_kitchen_source: 'USER_PROVIDED' | null;
  indoor_sound_observation: string | null;
  indoor_sound_observation_source: 'USER_PROVIDED' | null;
  indoor_sound_observation_unknown: string | null;
  grocery_external_id: string | null;
  grocery_name: string | null;
  grocery_identity: string | null;
  grocery_lng: number | null;
  grocery_lat: number | null;
  grocery_walking_minutes: number | null;
  living_meaning: string | null;
  current_judgment: string | null;
  decision_readiness: 'NEED_MORE_REALITY' | 'DECISION_READY' | null;
  decision_readiness_reason: string | null;
  meaningful_unknown: string | null;
  meaningful_unknown_why: string | null;
  reality_action_type: 'PUBLIC_EVIDENCE' | 'USER_REALITY' | null;
  reality_action_label: string | null;
  reality_action_why: string | null;
  public_rent_evidence: {
    source_reference: string;
    source_title: string;
    source_provider: string;
    property_text: string;
    observed_at: string;
    published_at: string | null;
  } | null;
  public_action_outcome: 'NO_EVIDENCE' | null;
  feedback_move_type: 'USER_REALITY' | 'SHIFT_ATTENTION' | null;
  feedback_move_label: string | null;
  feedback_move_why: string | null;
  area: number | null;
  bedrooms: number | null;
  bathrooms: number | null;
  commute_minutes: number | null;
  commute_mode: 'WALKING' | 'PUBLIC_TRANSIT' | null;
  pet_friendly: boolean | null;
  decision_state: 'ACTIVE' | 'WEAKENED' | 'REJECTED';
  state_reason: string | null;
  geographic_identity: string | null;
  geographic_precision: 'PLACE' | 'COMMUNITY' | 'STREET' | 'AREA' | null;
  geographic_status: 'UNRESOLVED' | 'GROUNDED';
  lng: number | null;
  lat: number | null;
}

export type PropertyInput = Omit<
  Property,
  | 'id'
  | 'conversation_id'
  | 'decision_state'
  | 'state_reason'
  | 'commute_mode'
  | 'rent_source'
  | 'rent_source_reference'
  | 'rent_observed_at'
  | 'independent_kitchen'
  | 'independent_kitchen_source'
  | 'indoor_sound_observation'
  | 'indoor_sound_observation_source'
  | 'indoor_sound_observation_unknown'
  | 'grocery_external_id'
  | 'grocery_name'
  | 'grocery_identity'
  | 'grocery_lng'
  | 'grocery_lat'
  | 'grocery_walking_minutes'
  | 'living_meaning'
  | 'current_judgment'
  | 'decision_readiness'
  | 'decision_readiness_reason'
  | 'meaningful_unknown'
  | 'meaningful_unknown_why'
  | 'reality_action_type'
  | 'reality_action_label'
  | 'reality_action_why'
  | 'public_rent_evidence'
  | 'public_action_outcome'
  | 'feedback_move_type'
  | 'feedback_move_label'
  | 'feedback_move_why'
  | 'geographic_identity'
  | 'geographic_precision'
  | 'geographic_status'
  | 'lng'
  | 'lat'
>;

interface PropertyListResponse {
  items: Property[];
}

export async function getProperties(
  conversationId: string,
  signal?: AbortSignal,
): Promise<Property[]> {
  const response = await apiRequest(
    `/properties?conversation_id=${encodeURIComponent(conversationId)}`,
    {
      method: 'GET',
      cache: 'no-store',
      signal,
    },
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch properties: ${response.status}`);
  }

  const data = (await response.json()) as PropertyListResponse;

  return data.items;
}

export async function getProperty(
  conversationId: string,
): Promise<Property | null> {
  const properties = await getProperties(conversationId);

  return properties[properties.length - 1] ?? null;
}

export async function acquireExternalRent(
  conversationId: string,
  propertyId: string,
): Promise<{ status: 'UPDATED' | 'NO_RELIABLE_EVIDENCE' | 'NOT_FOUND'; property: Property | null }> {
  const response = await apiRequest(
    `/properties/${encodeURIComponent(propertyId)}/external-rent`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ conversation_id: conversationId }),
    },
  );
  if (!response.ok) {
    throw new Error(`Failed to acquire external rent: ${response.status}`);
  }
  return response.json();
}

export async function executePublicRentAction(
  conversationId: string,
  propertyId: string,
): Promise<{ status: 'EVIDENCE_READY' | 'NO_EVIDENCE' | 'NOT_AVAILABLE'; property: Property | null }> {
  const response = await apiRequest(
    `/properties/${encodeURIComponent(propertyId)}/public-rent-evidence`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ conversation_id: conversationId }),
    },
  );
  if (!response.ok) throw new Error(`Failed to execute public rent action: ${response.status}`);
  return response.json();
}

export async function establishDailyGrocery(
  conversationId: string,
  propertyId: string,
): Promise<{ status: string; property: Property | null }> {
  const response = await apiRequest(
    `/properties/${encodeURIComponent(propertyId)}/daily-grocery`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ conversation_id: conversationId }),
    },
  );
  if (!response.ok) {
    throw new Error(`Failed to establish daily grocery: ${response.status}`);
  }
  return response.json();
}

export async function formLivingMeaning(
  conversationId: string,
  propertyId: string,
): Promise<{ status: string; property: Property | null }> {
  const response = await apiRequest(
    `/properties/${encodeURIComponent(propertyId)}/living-meaning`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ conversation_id: conversationId }),
    },
  );
  if (!response.ok) {
    throw new Error(`Failed to form Living Meaning: ${response.status}`);
  }
  return response.json();
}

export async function createProperty(
  conversationId: string,
  property: PropertyInput,
): Promise<Property> {
  const response = await apiRequest('/properties', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      conversation_id: conversationId,
      ...property,
    }),
  });

  if (!response.ok) {
    throw new Error(`Failed to create property: ${response.status}`);
  }

  return response.json() as Promise<Property>;
}

export async function deleteProperty(propertyId: string): Promise<void> {
  const response = await apiRequest(
    `/properties/${encodeURIComponent(propertyId)}`,
    {
      method: 'DELETE',
    },
  );

  if (!response.ok) {
    throw new Error(`Failed to delete property: ${response.status}`);
  }
}
