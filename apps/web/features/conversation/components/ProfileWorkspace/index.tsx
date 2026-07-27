import type { LivingProfile } from '@/services/profile';

interface ProfileWorkspaceProps {
    profile: LivingProfile | null;
    isLoading: boolean;
}

interface ProfileItem {
    key: keyof Omit<LivingProfile, 'conversation_id'>;
    label: string;
    value: string;
    icon: string;
    isKnown: boolean;
}

const LEARNING_TEXT = '持续了解中…';

function getProfileItems(
    profile: LivingProfile | null,
): ProfileItem[] {
    return [
        {
            key: 'work_location',
            icon: '📍',
            label: '工作地点',
            value: profile?.work_location || LEARNING_TEXT,
            isKnown: Boolean(profile?.work_location),
        },
        {
            key: 'budget',
            icon: '💰',
            label: '预算',
            value:
                profile?.budget !== null &&
                    profile?.budget !== undefined
                    ? `¥${profile.budget.toLocaleString('zh-CN')}`
                    : LEARNING_TEXT,
            isKnown:
                profile?.budget !== null &&
                profile?.budget !== undefined,
        },
        {
            key: 'commute_minutes',
            icon: '🚇',
            label: '通勤要求',
            value:
                profile?.commute_minutes !== null &&
                    profile?.commute_minutes !== undefined
                    ? `不超过 ${profile.commute_minutes} 分钟`
                    : LEARNING_TEXT,
            isKnown:
                profile?.commute_minutes !== null &&
                profile?.commute_minutes !== undefined,
        },
        {
            key: 'preferred_city',
            icon: '🏙️',
            label: '意向城市',
            value: profile?.preferred_city || LEARNING_TEXT,
            isKnown: Boolean(profile?.preferred_city),
        },
        {
            key: 'family_size',
            icon: '👥',
            label: '家庭人数',
            value:
                profile?.family_size !== null &&
                    profile?.family_size !== undefined
                    ? `${profile.family_size} 人`
                    : LEARNING_TEXT,
            isKnown:
                profile?.family_size !== null &&
                profile?.family_size !== undefined,
        },
        {
            key: 'has_pet',
            icon: '🐾',
            label: '宠物情况',
            value:
                profile?.has_pet === null ||
                    profile?.has_pet === undefined
                    ? LEARNING_TEXT
                    : profile.has_pet
                        ? '有宠物'
                        : '无宠物',
            isKnown:
                profile?.has_pet !== null &&
                profile?.has_pet !== undefined,
        },
    ];
}

export default function ProfileWorkspace({
    profile,
    isLoading,
}: ProfileWorkspaceProps) {
    const items = getProfileItems(profile);
    const knownCount = items.filter((item) => item.isKnown).length;
    const completion = Math.round(
        (knownCount / items.length) * 100,
    );

    return (
        <aside className="overflow-hidden rounded-3xl border border-white/10 bg-white/[0.04]">
            <header className="border-b border-white/10 p-5">
                <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                        <span
                            aria-hidden="true"
                            className={[
                                'h-2 w-2 rounded-full',
                                isLoading
                                    ? 'animate-pulse bg-white/50'
                                    : profile
                                        ? 'bg-white'
                                        : 'bg-white/20',
                            ].join(' ')}
                        />

                        <p className="text-xs font-medium uppercase tracking-[0.2em] text-neutral-500">
                            AI 理解
                        </p>
                    </div>

                    <ProfileStatus
                        profile={profile}
                        isLoading={isLoading}
                    />
                </div>

                <h2 className="mt-3 text-xl font-medium tracking-tight text-white">
                    你的居住画像
                </h2>

                <p className="mt-2 text-sm leading-6 text-neutral-400">
                    LiveOS 会随着对话持续理解你的居住需求、约束与偏好。
                </p>

                {!isLoading && profile && (
                    <div className="mt-5">
                        <div className="flex items-center justify-between text-xs text-neutral-500">
                            <span>画像完整度</span>
                            <span>{completion}%</span>
                        </div>

                        <div className="mt-2 h-1 overflow-hidden rounded-full bg-white/10">
                            <div
                                className="h-full rounded-full bg-white/70 transition-[width] duration-500"
                                style={{
                                    width: `${completion}%`,
                                }}
                            />
                        </div>
                    </div>
                )}
            </header>

            {isLoading ? (
                <ProfileLoadingState />
            ) : (
                <div className="divide-y divide-white/10 px-5">
                    {items.map((item) => (
                        <ProfileItemRow
                            key={item.key}
                            item={item}
                        />
                    ))}
                </div>
            )}

            <footer className="border-t border-white/10 px-5 py-4">
                <p className="text-xs leading-5 text-neutral-500">
                    {profile
                        ? '随着对话继续，你的居住画像会逐步补充和更新。'
                        : '开始对话后，LiveOS 会在这里呈现对你的理解。'}
                </p>
            </footer>
        </aside>
    );
}

interface ProfileStatusProps {
    profile: LivingProfile | null;
    isLoading: boolean;
}

function ProfileStatus({
    profile,
    isLoading,
}: ProfileStatusProps) {
    const text = isLoading
        ? '同步中'
        : profile
            ? '已同步'
            : '等待信息';

    return (
        <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[10px] text-neutral-400">
            {text}
        </span>
    );
}

interface ProfileItemRowProps {
    item: ProfileItem;
}

function ProfileItemRow({
    item,
}: ProfileItemRowProps) {
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
                        'mt-1 truncate text-sm transition-colors',
                        item.isKnown
                            ? 'font-medium text-neutral-200'
                            : 'italic text-neutral-600',
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
            role="status"
            aria-live="polite"
            aria-label="正在同步居住画像"
            className="space-y-4 px-5 py-5"
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