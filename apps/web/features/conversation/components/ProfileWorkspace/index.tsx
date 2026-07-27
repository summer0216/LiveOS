import type { LivingProfile } from '@/services/profile';

interface ProfileWorkspaceProps {
    profile: LivingProfile | null;
    isLoading: boolean;
}

interface ProfileItem {
    label: string;
    value: string;
    icon: string;
}

const LEARNING_TEXT = 'Still learning...';

function getProfileItems(
    profile: LivingProfile | null,
): ProfileItem[] {
    return [
        {
            icon: '📍',
            label: 'Work',
            value: profile?.work_location || LEARNING_TEXT,
        },
        {
            icon: '💰',
            label: 'Budget',
            value:
                profile?.budget !== null &&
                    profile?.budget !== undefined
                    ? `¥${profile.budget.toLocaleString('zh-CN')}`
                    : LEARNING_TEXT,
        },
        {
            icon: '🚇',
            label: 'Commute',
            value:
                profile?.commute_minutes !== null &&
                    profile?.commute_minutes !== undefined
                    ? `≤ ${profile.commute_minutes} min`
                    : LEARNING_TEXT,
        },
        {
            icon: '🏙️',
            label: 'Preferred City',
            value: profile?.preferred_city || LEARNING_TEXT,
        },
        {
            icon: '👥',
            label: 'Household',
            value:
                profile?.family_size !== null &&
                    profile?.family_size !== undefined
                    ? `${profile.family_size} people`
                    : LEARNING_TEXT,
        },
        {
            icon: '🐾',
            label: 'Lifestyle',
            value:
                profile?.has_pet === null ||
                    profile?.has_pet === undefined
                    ? LEARNING_TEXT
                    : profile.has_pet
                        ? 'Pet owner'
                        : 'No pets',
        },
    ];
}

export default function ProfileWorkspace({
    profile,
    isLoading,
}: ProfileWorkspaceProps) {
    const items = getProfileItems(profile);

    return (
        <aside className="rounded-3xl border border-white/10 bg-white/[0.04] p-5">
            <header className="border-b border-white/10 pb-5">
                <div className="flex items-center justify-between gap-3">
                    <p className="text-xs font-medium uppercase tracking-[0.2em] text-neutral-500">
                        AI Understanding
                    </p>

                    {!isLoading && profile && (
                        <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[10px] text-neutral-400">
                            Updated
                        </span>
                    )}
                </div>

                <h2 className="mt-3 text-xl font-medium tracking-tight text-white">
                    Your Living Profile
                </h2>

                <p className="mt-2 text-sm leading-6 text-neutral-400">
                    LiveOS is building an understanding of your living
                    needs as the conversation develops.
                </p>
            </header>

            {isLoading ? (
                <ProfileLoadingState />
            ) : (
                <div className="divide-y divide-white/10">
                    {items.map((item) => (
                        <ProfileItemRow
                            key={item.label}
                            item={item}
                        />
                    ))}
                </div>
            )}

            <footer className="border-t border-white/10 pt-4">
                <p className="text-xs leading-5 text-neutral-500">
                    Your profile will continue to evolve as LiveOS learns
                    more about your priorities.
                </p>
            </footer>
        </aside>
    );
}

interface ProfileItemRowProps {
    item: ProfileItem;
}

function ProfileItemRow({
    item,
}: ProfileItemRowProps) {
    const isLearning = item.value === LEARNING_TEXT;

    return (
        <div className="flex gap-3 py-4">
            <div
                aria-hidden="true"
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-base"
            >
                {item.icon}
            </div>

            <div className="min-w-0 flex-1">
                <p className="text-xs text-neutral-500">
                    {item.label}
                </p>

                <p
                    className={[
                        'mt-1 truncate text-sm',
                        isLearning
                            ? 'italic text-neutral-600'
                            : 'font-medium text-neutral-200',
                    ].join(' ')}
                >
                    {item.value}
                </p>
            </div>
        </div>
    );
}

function ProfileLoadingState() {
    return (
        <div
            aria-label="Loading living profile"
            className="space-y-4 py-5"
        >
            {[0, 1, 2, 3].map((item) => (
                <div
                    key={item}
                    className="flex animate-pulse gap-3"
                >
                    <div className="h-9 w-9 rounded-xl bg-white/5" />

                    <div className="flex-1 space-y-2">
                        <div className="h-3 w-20 rounded bg-white/5" />
                        <div className="h-4 w-32 rounded bg-white/10" />
                    </div>
                </div>
            ))}
        </div>
    );
}