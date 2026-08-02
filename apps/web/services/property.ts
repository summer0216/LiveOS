import { apiRequest } from '@/services/api';

export interface Property {
  id: string;
  conversation_id: string;
  title: string | null;
  district: string | null;
  rent: number | null;
  area: number | null;
  bedrooms: number | null;
  bathrooms: number | null;
  commute_minutes: number | null;
  pet_friendly: boolean | null;
}

export type PropertyInput = Omit<Property, 'id' | 'conversation_id'>;

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
