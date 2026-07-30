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

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8000';

export async function getProperties(
  conversationId: string,
): Promise<Property[]> {
  const response = await fetch(
    `${API_BASE_URL}/api/properties?conversation_id=${encodeURIComponent(conversationId)}`,
    {
      method: 'GET',
      cache: 'no-store',
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
  const response = await fetch(`${API_BASE_URL}/api/properties`, {
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
  const response = await fetch(
    `${API_BASE_URL}/api/properties/${encodeURIComponent(propertyId)}`,
    {
      method: 'DELETE',
    },
  );

  if (!response.ok) {
    throw new Error(`Failed to delete property: ${response.status}`);
  }
}
