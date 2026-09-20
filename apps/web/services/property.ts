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
