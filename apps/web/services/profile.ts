import { apiRequest } from '@/services/api';

export const PROFILE_TAG_CATEGORIES = [
    'preference',
    'commute',
    'lifestyle',
    'budget',
] as const;

export type ProfileTagCategory =
    (typeof PROFILE_TAG_CATEGORIES)[number];

export type PreferenceTags = Record<
    ProfileTagCategory,
    string[]
>;

export interface LivingProfile {
    conversation_id: string;
    work_location: string | null;
    budget: number | null;
    commute_minutes: number | null;
    preferred_city: string | null;
    family_size: number | null;
    has_pet: boolean | null;
    latest_insights: string[];
    preference_tags: PreferenceTags;
}

export async function updatePreferenceTags(
    conversationId: string,
    preferenceTags: PreferenceTags,
): Promise<LivingProfile> {
    const response = await apiRequest(
        `/profiles/${encodeURIComponent(conversationId)}/tags`,
        {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                preference_tags: preferenceTags,
            }),
        },
    );

    if (!response.ok) {
        throw new Error(
            `Failed to update preference tags: ${response.status}`,
        );
    }

    return response.json() as Promise<LivingProfile>;
}

export async function getLivingProfile(
    conversationId: string,
): Promise<LivingProfile | null> {
    const response = await apiRequest(
        `/profiles/${encodeURIComponent(conversationId)}`,
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
