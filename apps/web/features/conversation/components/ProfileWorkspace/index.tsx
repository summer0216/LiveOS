import type { LivingProfile } from '@/services/profile';

interface ProfileWorkspaceProps {
    profile: LivingProfile | null;
    isLoading: boolean;
}

function displayValue(
    value: string | number | null,
    suffix = '',
) {
    if (value === null || value === '') {
        return 'Unknown';
    }

    return `${value}${suffix}`;
}

export default function ProfileWorkspace({
    profile,
    isLoading,
}: ProfileWorkspaceProps) {
    return (
        <aside className="rounded-3xl border border-white/10 bg-white/5 p-5">
            <div className="mb-5">
                <p className="text-xs uppercase tracking-[0.2em] text-neutral-500">
                    AI Understanding
                </p>

                <h2 className="mt-2 text-lg font-medium text-white">
                    Living Profile
                </h2>
            </div>

            {isLoading ? (
                <p className="text-sm text-neutral-500">
                    Reading profile...
                </p>
            ) : (
                <div className="space-y-4">
                    <ProfileRow
                        label="Work Location"
                        value={displayValue(profile?.work_location ?? null)}
                    />

                    <ProfileRow
                        label="Budget"
                        value={
                            profile?.budget !== null &&
                                profile?.budget !== undefined
                                ? `¥${profile.budget}`
                                : 'Unknown'
                        }
                    />

                    <ProfileRow
                        label="Commute"
                        value={displayValue(
                            profile?.commute_minutes ?? null,
                            ' min',
                        )}
                    />

                    <ProfileRow
                        label="Preferred City"
                        value={displayValue(
                            profile?.preferred_city ?? null,
                        )}
                    />

                    <ProfileRow
                        label="Family Size"
                        value={displayValue(
                            profile?.family_size ?? null,
                        )}
                    />

                    <ProfileRow
                        label="Pet"
                        value={
                            profile?.has_pet === null ||
                                profile?.has_pet === undefined
                                ? 'Unknown'
                                : profile.has_pet
                                    ? 'Yes'
                                    : 'No'
                        }
                    />
                </div>
            )}
        </aside>
    );
}

interface ProfileRowProps {
    label: string;
    value: string;
}

function ProfileRow({
    label,
    value,
}: ProfileRowProps) {
    return (
        <div className="border-b border-white/10 pb-3 last:border-b-0 last:pb-0">
            <p className="text-xs text-neutral-500">{label}</p>
            <p className="mt-1 text-sm text-neutral-200">{value}</p>
        </div>
    );
}