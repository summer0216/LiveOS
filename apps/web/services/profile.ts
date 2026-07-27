export interface LivingProfile {
    conversation_id: string;
    work_location: string | null;
    budget: number | null;
    commute_minutes: number | null;
    preferred_city: string | null;
    family_size: number | null;
    has_pet: boolean | null;
}

const API_BASE_URL =
    process.env.NEXT_PUBLIC_API_BASE_URL ??
    'http://127.0.0.1:8000';

export async function getLivingProfile(
    conversationId: string,
): Promise<LivingProfile | null> {
    const response = await fetch(
        `${API_BASE_URL}/api/profiles/${conversationId}`,
        {
            method: 'GET',
            cache: 'no-store',
        },
    );

    // Profile 尚未创建时，不视为页面错误
    if (response.status === 404) {
        return null;
    }

    if (!response.ok) {
        throw new Error(
            `Failed to fetch living profile: ${response.status}`,
        );
    }

    return response.json() as Promise<LivingProfile>;
}