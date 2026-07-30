export interface Property {
  title: string | null;
  district: string | null;
  rent: number | null;
  area: number | null;
  bedrooms: number | null;
  bathrooms: number | null;
  commute_minutes: number | null;
  pet_friendly: boolean | null;
}

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8000';

export async function getProperty(
  conversationId: string,
): Promise<Property | null> {
  const response = await fetch(
    `${API_BASE_URL}/api/properties/${conversationId}`,
    {
      method: 'GET',
      cache: 'no-store',
    },
  );

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    throw new Error(`Failed to fetch property: ${response.status}`);
  }

  return response.json() as Promise<Property>;
}
