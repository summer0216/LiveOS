'use client';

import {
    useEffect,
    useMemo,
    useRef,
    useState,
} from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import {
    ArrowRight,
    Check,
    Plus,
    Sparkles,
    X,
} from 'lucide-react';

import {
    getLivingProfile,
    updatePreferenceTags,
    type LivingProfile,
    type PreferenceTags,
    type ProfileTagCategory,
} from '@/services/profile';

const JOURNEY_STEPS = [
    '入口',
    '对话',
    '生活模型',
    '工作台',
    '详情',
    '对比',
    '决策',
    '记忆',
] as const;

interface ProfileCardData {
    icon: string;
    title: string;
    items: string[];
}

interface TagGroup {
    category: ProfileTagCategory;
    label: string;
    tone: 'neutral' | 'blue' | 'violet' | 'green';
    items: string[];
}

const TAG_GROUP_CONFIG: Array<
    Omit<TagGroup, 'items'>
> = [
    {
        category: 'preference',
        label: '偏好',
        tone: 'neutral',
    },
    {
        category: 'commute',
        label: '通勤',
        tone: 'blue',
    },
    {
        category: 'lifestyle',
        label: '生活',
        tone: 'violet',
    },
    {
        category: 'budget',
        label: '预算',
        tone: 'green',
    },
];

const tagToneClasses: Record<TagGroup['tone'], string> = {
    neutral: 'border-slate-600/60 bg-slate-900/60 text-slate-300',
    blue: 'border-blue-500/50 bg-blue-500/5 text-blue-300',
    violet: 'border-violet-500/50 bg-violet-500/5 text-violet-300',
    green: 'border-emerald-500/50 bg-emerald-500/5 text-emerald-300',
};

function formatBudget(budget: number): string {
    return `$${budget.toLocaleString('en-US')}/月`;
}

function getProfileCards(profile: LivingProfile): ProfileCardData[] {
    const housingItems = [
        profile.preferred_city
            ? `意向城市：${profile.preferred_city}`
            : null,
        profile.family_size
            ? `${profile.family_size} 人居住`
            : null,
        profile.has_pet === null
            ? null
            : profile.has_pet
              ? '需要宠物友好住宅'
              : '无需宠物空间',
    ].filter((item): item is string => item !== null);

    const lifestyleItems = [
        profile.family_size
            ? `${profile.family_size} 人生活空间`
            : null,
        profile.has_pet === null
            ? null
            : profile.has_pet
              ? '与宠物共同生活'
              : '暂无宠物需求',
    ].filter((item): item is string => item !== null);

    const commuteItems = [
        profile.work_location
            ? `目的地：${profile.work_location}`
            : null,
        profile.commute_minutes
            ? `最长接受：${profile.commute_minutes} 分钟`
            : null,
    ].filter((item): item is string => item !== null);

    const budgetItems = [
        profile.budget
            ? `租金上限：${formatBudget(profile.budget)}`
            : null,
    ].filter((item): item is string => item !== null);

    return [
        { icon: '🏠', title: '住房', items: housingItems },
        { icon: '🚲', title: '生活方式', items: lifestyleItems },
        { icon: '🚇', title: '通勤', items: commuteItems },
        { icon: '💰', title: '预算', items: budgetItems },
    ];
}

function clonePreferenceTags(
    preferenceTags: PreferenceTags,
): PreferenceTags {
    return {
        preference: [...preferenceTags.preference],
        commute: [...preferenceTags.commute],
        lifestyle: [...preferenceTags.lifestyle],
        budget: [...preferenceTags.budget],
    };
}

function createEmptyPreferenceTags(): PreferenceTags {
    return {
        preference: [],
        commute: [],
        lifestyle: [],
        budget: [],
    };
}

function getTagGroups(
    preferenceTags: PreferenceTags,
): TagGroup[] {
    return TAG_GROUP_CONFIG.map((group) => ({
        ...group,
        items: preferenceTags[group.category],
    }));
}

export default function ProfileFeature() {
    const searchParams = useSearchParams();
    const conversationId = searchParams.get('conversation_id') ?? '';
    const [profile, setProfile] = useState<LivingProfile | null>(null);
    const [isLoading, setIsLoading] = useState(Boolean(conversationId));
    const [hasError, setHasError] = useState(false);
    const [isEditing, setIsEditing] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [editingCategory, setEditingCategory] =
        useState<ProfileTagCategory | null>(null);
    const [draftTags, setDraftTags] = useState<PreferenceTags>(
        createEmptyPreferenceTags,
    );
    const [originalTags, setOriginalTags] =
        useState<PreferenceTags>(createEmptyPreferenceTags);
    const [saveError, setSaveError] = useState<string | null>(null);

    useEffect(() => {
        let isActive = true;

        async function loadProfile() {
            if (!conversationId) {
                setIsLoading(false);
                return;
            }

            setIsLoading(true);
            setHasError(false);

            try {
                const nextProfile =
                    await getLivingProfile(conversationId);

                if (isActive) {
                    setProfile(nextProfile);

                    if (nextProfile) {
                        const nextTags = clonePreferenceTags(
                            nextProfile.preference_tags,
                        );
                        setDraftTags(nextTags);
                        setOriginalTags(nextTags);
                    }
                }
            } catch (error: unknown) {
                console.error('Failed to load living profile:', error);

                if (isActive) {
                    setHasError(true);
                }
            } finally {
                if (isActive) {
                    setIsLoading(false);
                }
            }
        }

        void loadProfile();

        return () => {
            isActive = false;
        };
    }, [conversationId]);

    const cards = useMemo(
        () => (profile ? getProfileCards(profile) : []),
        [profile],
    );
    const tagGroups = useMemo(
        () => getTagGroups(draftTags),
        [draftTags],
    );

    const conversationHref = conversationId
        ? `/conversation?conversation_id=${encodeURIComponent(conversationId)}`
        : '/';

    function beginEditing() {
        if (!profile) {
            return;
        }

        const currentTags = clonePreferenceTags(
            profile.preference_tags,
        );
        setDraftTags(currentTags);
        setOriginalTags(currentTags);
        setEditingCategory(null);
        setSaveError(null);
        setIsEditing(true);
    }

    function removeTag(
        category: ProfileTagCategory,
        tag: string,
    ) {
        setDraftTags((currentTags) => ({
            ...currentTags,
            [category]: currentTags[category].filter(
                (currentTag) => currentTag !== tag,
            ),
        }));
    }

    function addTag(
        category: ProfileTagCategory,
        tag: string,
    ): boolean {
        const normalizedTag = tag.trim();

        if (
            !normalizedTag ||
            draftTags[category].includes(normalizedTag)
        ) {
            return false;
        }

        setDraftTags((currentTags) => ({
            ...currentTags,
            [category]: [
                ...currentTags[category],
                normalizedTag,
            ],
        }));
        setEditingCategory(null);
        return true;
    }

    async function completeEditing() {
        if (!conversationId || isSaving) {
            return;
        }

        setIsSaving(true);
        setSaveError(null);
        setEditingCategory(null);

        try {
            const updatedProfile = await updatePreferenceTags(
                conversationId,
                draftTags,
            );
            const updatedTags = clonePreferenceTags(
                updatedProfile.preference_tags,
            );

            setProfile(updatedProfile);
            setDraftTags(updatedTags);
            setOriginalTags(updatedTags);
            setIsEditing(false);
        } catch (error: unknown) {
            console.error(
                'Failed to update preference tags:',
                error,
            );
            setDraftTags(clonePreferenceTags(originalTags));
            setSaveError(
                '标签保存失败，已恢复到编辑前的内容，请重试。',
            );
        } finally {
            setIsSaving(false);
        }
    }

    return (
        <main className="min-h-screen bg-[#050812] text-slate-100">
            <div className="min-h-screen bg-[radial-gradient(circle_at_center,rgba(78,91,168,0.08)_0,transparent_46%),radial-gradient(rgba(91,112,180,0.09)_1px,transparent_1px)] bg-[size:auto,28px_28px]">
                <JourneyHeader />

                <div className="mx-auto w-full max-w-[1180px] px-5 pb-12 pt-8 sm:px-8 lg:pt-10">
                    <ProfileHeading
                        isEditing={isEditing}
                        isSaving={isSaving}
                        canEdit={Boolean(profile)}
                        onEdit={beginEditing}
                        onComplete={() => {
                            void completeEditing();
                        }}
                    />

                    {saveError && (
                        <div
                            role="alert"
                            className="mt-5 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300"
                        >
                            {saveError}
                        </div>
                    )}

                    {isLoading ? (
                        <ProfileLoadingState />
                    ) : profile ? (
                        <ProfileLoadedState
                            cards={cards}
                            profile={profile}
                            tagGroups={tagGroups}
                            isEditing={isEditing}
                            editingCategory={editingCategory}
                            onAddStart={setEditingCategory}
                            onAddCancel={() => {
                                setEditingCategory(null);
                            }}
                            onAdd={addTag}
                            onRemove={removeTag}
                        />
                    ) : (
                        <ProfileEmptyState
                            conversationHref={conversationHref}
                            hasError={hasError}
                        />
                    )}
                </div>
            </div>
        </main>
    );
}

function JourneyHeader() {
    return (
        <header className="border-b border-white/[0.06] bg-[#050812]/95">
            <div className="mx-auto flex h-[72px] max-w-[1480px] items-center gap-8 px-5 sm:px-8">
                <Link
                    href="/"
                    aria-label="返回 LiveOS 首页"
                    className="flex shrink-0 items-center gap-2.5"
                >
                    <span className="h-9 w-9 rounded-full bg-[radial-gradient(circle_at_35%_30%,#8d78ff_0,#5265dd_48%,#1a275a_100%)] shadow-[0_0_24px_rgba(93,91,255,0.35)]" />
                    <span className="text-lg font-semibold tracking-tight">
                        Live<span className="text-blue-500">OS</span>
                    </span>
                </Link>

                <nav
                    aria-label="LiveOS 决策旅程"
                    className="hidden min-w-0 flex-1 items-center justify-center xl:flex"
                >
                    {JOURNEY_STEPS.map((step, index) => {
                        const stepNumber = index + 1;
                        const isComplete = stepNumber < 3;
                        const isCurrent = stepNumber === 3;

                        return (
                            <div
                                key={step}
                                className="flex items-center"
                            >
                                <div
                                    className={[
                                        'flex items-center gap-2 text-sm',
                                        isCurrent
                                            ? 'font-medium text-slate-100'
                                            : isComplete
                                              ? 'text-blue-400'
                                              : 'text-slate-600',
                                    ].join(' ')}
                                >
                                    <span
                                        className={[
                                            'flex h-7 w-7 items-center justify-center rounded-full border text-xs',
                                            isCurrent
                                                ? 'border-blue-500 bg-blue-500 text-white'
                                                : isComplete
                                                  ? 'border-blue-500/70 bg-blue-500/10'
                                                  : 'border-slate-800 bg-slate-900/70',
                                        ].join(' ')}
                                    >
                                        {isComplete ? (
                                            <Check size={14} />
                                        ) : (
                                            stepNumber
                                        )}
                                    </span>
                                    <span>{step}</span>
                                </div>

                                {index < JOURNEY_STEPS.length - 1 && (
                                    <span className="mx-3 h-px w-5 bg-slate-800" />
                                )}
                            </div>
                        );
                    })}
                </nav>

                <div className="ml-auto flex shrink-0 items-center gap-3">
                    <span className="hidden rounded-xl border border-white/10 px-4 py-2 text-sm text-slate-400 sm:inline">
                        工作台
                    </span>
                    <span className="flex h-9 w-9 items-center justify-center rounded-full bg-violet-500 text-sm font-medium text-white">
                        我
                    </span>
                </div>
            </div>
        </header>
    );
}

function ProfileHeading({
    isEditing,
    isSaving,
    canEdit,
    onEdit,
    onComplete,
}: {
    isEditing: boolean;
    isSaving: boolean;
    canEdit: boolean;
    onEdit: () => void;
    onComplete: () => void;
}) {
    return (
        <section className="flex flex-col justify-between gap-6 lg:flex-row lg:items-center">
            <div>
                <p className="font-mono text-xs tracking-[0.16em] text-blue-400">
                    生活模型 · AI 生成
                </p>
                <h1 className="mt-5 text-3xl font-semibold tracking-tight text-slate-100 sm:text-4xl">
                    你的偏好，我已读懂。
                </h1>
                <p className="mt-3 text-base text-slate-500">
                    查看并完善我对你理想居住情况的理解。
                </p>
            </div>

            <div className="flex items-center gap-3">
                <button
                    type="button"
                    disabled={!canEdit || isSaving}
                    onClick={isEditing ? onComplete : onEdit}
                    className="rounded-xl border border-white/10 bg-black/10 px-6 py-3.5 text-sm text-slate-400 transition hover:border-white/20 hover:text-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
                >
                    {isSaving
                        ? '保存中…'
                        : isEditing
                          ? '完成编辑'
                          : '编辑生活模型'}
                </button>
                <button
                    type="button"
                    disabled
                    title="将在 P04 工作台实现"
                    className="flex cursor-not-allowed items-center gap-2 rounded-xl bg-blue-500 px-6 py-3.5 text-sm font-medium text-white opacity-80 shadow-[0_12px_30px_rgba(59,105,255,0.2)]"
                >
                    查找房源
                    <ArrowRight size={16} />
                </button>
            </div>
        </section>
    );
}

function ProfileLoadedState({
    cards,
    profile,
    tagGroups,
    isEditing,
    editingCategory,
    onAddStart,
    onAddCancel,
    onAdd,
    onRemove,
}: {
    cards: ProfileCardData[];
    profile: LivingProfile;
    tagGroups: TagGroup[];
    isEditing: boolean;
    editingCategory: ProfileTagCategory | null;
    onAddStart: (category: ProfileTagCategory) => void;
    onAddCancel: () => void;
    onAdd: (
        category: ProfileTagCategory,
        tag: string,
    ) => boolean;
    onRemove: (
        category: ProfileTagCategory,
        tag: string,
    ) => void;
}) {
    const tagCount = tagGroups.reduce(
        (count, group) => count + group.items.length,
        0,
    );

    return (
        <div className="mt-12 space-y-8">
            <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                {cards.map((card) => (
                    <article
                        key={card.title}
                        className="min-h-[220px] rounded-2xl border border-white/[0.08] bg-[#0b1020]/90 p-6"
                    >
                        <span
                            aria-hidden="true"
                            className="text-2xl"
                        >
                            {card.icon}
                        </span>
                        <h2 className="mt-6 text-base font-medium text-slate-200">
                            {card.title}
                        </h2>
                        {card.items.length > 0 ? (
                            <ul className="mt-4 space-y-2.5">
                                {card.items.map((item) => (
                                    <li
                                        key={item}
                                        className="flex gap-2 text-sm leading-5 text-slate-500"
                                    >
                                        <span className="text-blue-500">
                                            •
                                        </span>
                                        <span>{item}</span>
                                    </li>
                                ))}
                            </ul>
                        ) : (
                            <p className="mt-4 text-sm leading-6 text-slate-600">
                                继续对话以补充信息
                            </p>
                        )}
                    </article>
                ))}
            </section>

            <section className="rounded-2xl border border-white/[0.08] bg-[#0b1020]/90 p-6 sm:p-7">
                <div className="flex items-center justify-between gap-4">
                    <h2 className="text-base font-medium text-slate-200">
                        偏好标签
                    </h2>
                    <span className="font-mono text-xs text-slate-600">
                        已捕捉 {tagCount} 条
                    </span>
                </div>

                <div className="mt-6 space-y-4">
                    {tagGroups.map((group) => (
                        <div
                            key={group.label}
                            className="grid gap-3 sm:grid-cols-[58px_1fr] sm:items-start"
                        >
                            <span
                                className={[
                                    'pt-2 font-mono text-xs',
                                    group.tone === 'blue'
                                        ? 'text-blue-400'
                                        : group.tone === 'violet'
                                          ? 'text-violet-400'
                                          : group.tone === 'green'
                                            ? 'text-emerald-400'
                                            : 'text-slate-500',
                                ].join(' ')}
                            >
                                {group.label}
                            </span>
                            <div className="flex min-h-8 flex-wrap gap-2">
                                {group.items.map((item) => (
                                    <span
                                        key={item}
                                        className={[
                                            'flex items-center rounded-full border px-3 py-1.5 font-mono text-xs',
                                            tagToneClasses[group.tone],
                                        ].join(' ')}
                                    >
                                        {item}
                                        {isEditing && (
                                            <button
                                                type="button"
                                                aria-label={`删除 ${item}`}
                                                onClick={() => {
                                                    onRemove(
                                                        group.category,
                                                        item,
                                                    );
                                                }}
                                                className="ml-2 rounded-full text-current opacity-60 transition hover:opacity-100"
                                            >
                                                <X size={12} />
                                            </button>
                                        )}
                                    </span>
                                ))}

                                {isEditing &&
                                    (editingCategory ===
                                    group.category ? (
                                        <InlineTagInput
                                            category={group.category}
                                            existingTags={group.items}
                                            tone={group.tone}
                                            onAdd={onAdd}
                                            onCancel={onAddCancel}
                                        />
                                    ) : (
                                        <button
                                            type="button"
                                            onClick={() => {
                                                onAddStart(
                                                    group.category,
                                                );
                                            }}
                                            className="flex items-center gap-1 rounded-full border border-dashed border-slate-700 px-3 py-1.5 font-mono text-xs text-slate-600 transition hover:border-slate-500 hover:text-slate-400"
                                        >
                                            <Plus size={12} />
                                            添加
                                        </button>
                                    ))}
                            </div>
                        </div>
                    ))}
                </div>
            </section>

            <section className="flex gap-4 rounded-2xl border border-blue-500/15 bg-[#0a1020]/90 px-6 py-5">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[radial-gradient(circle_at_35%_30%,#78baff_0,#4e85d9_40%,#3b9f81_100%)] shadow-[0_0_22px_rgba(68,150,180,0.3)]">
                    <Sparkles size={17} />
                </span>
                <div>
                    <h2 className="font-mono text-xs tracking-[0.12em] text-blue-400">
                        AI 洞察
                    </h2>
                    <p className="mt-2 text-sm leading-6 text-slate-400">
                        {profile.latest_insights.length > 0
                            ? profile.latest_insights.join('，') + '。'
                            : '你的生活模型已生成。继续对话，我会逐步完善对你的理解。'}
                    </p>
                </div>
            </section>
        </div>
    );
}

function InlineTagInput({
    category,
    existingTags,
    tone,
    onAdd,
    onCancel,
}: {
    category: ProfileTagCategory;
    existingTags: string[];
    tone: TagGroup['tone'];
    onAdd: (
        category: ProfileTagCategory,
        tag: string,
    ) => boolean;
    onCancel: () => void;
}) {
    const containerRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);
    const [value, setValue] = useState('');
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        inputRef.current?.focus();

        function handlePointerDown(event: PointerEvent) {
            if (
                containerRef.current &&
                !containerRef.current.contains(
                    event.target as Node,
                )
            ) {
                onCancel();
            }
        }

        document.addEventListener('pointerdown', handlePointerDown);

        return () => {
            document.removeEventListener(
                'pointerdown',
                handlePointerDown,
            );
        };
    }, [onCancel]);

    function submit() {
        const normalizedValue = value.trim();

        if (!normalizedValue) {
            setError('请输入标签');
            return;
        }

        if (existingTags.includes(normalizedValue)) {
            setError('标签已存在');
            return;
        }

        if (!onAdd(category, normalizedValue)) {
            setError('无法添加标签');
        }
    }

    return (
        <div
            ref={containerRef}
            className="relative"
        >
            <div
                className={[
                    'flex items-center rounded-full border pl-3 pr-1 py-1 font-mono text-xs',
                    tagToneClasses[tone],
                ].join(' ')}
            >
                <input
                    ref={inputRef}
                    value={value}
                    aria-label="新标签"
                    onChange={(event) => {
                        setValue(event.target.value);
                        setError(null);
                    }}
                    onKeyDown={(event) => {
                        if (event.key === 'Enter') {
                            event.preventDefault();
                            submit();
                        }

                        if (event.key === 'Escape') {
                            event.preventDefault();
                            onCancel();
                        }
                    }}
                    className="w-28 bg-transparent outline-none placeholder:text-slate-600"
                    placeholder="输入标签"
                />
                <button
                    type="button"
                    aria-label="确认添加标签"
                    onClick={submit}
                    className="flex h-6 w-6 items-center justify-center rounded-full hover:bg-white/10"
                >
                    <Check size={12} />
                </button>
            </div>
            {error && (
                <span className="absolute left-2 top-full mt-1 whitespace-nowrap text-[10px] text-red-400">
                    {error}
                </span>
            )}
        </div>
    );
}

function ProfileLoadingState() {
    return (
        <div
            role="status"
            aria-label="正在加载生活模型"
            className="mt-12 space-y-8"
        >
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                {[0, 1, 2, 3].map((item) => (
                    <div
                        key={item}
                        className="min-h-[220px] animate-pulse rounded-2xl border border-white/[0.06] bg-[#0b1020]/90 p-6"
                    >
                        <div className="h-7 w-7 rounded bg-white/10" />
                        <div className="mt-7 h-5 w-20 rounded bg-white/10" />
                        <div className="mt-5 h-3 w-4/5 rounded bg-white/[0.06]" />
                        <div className="mt-3 h-3 w-3/5 rounded bg-white/[0.06]" />
                    </div>
                ))}
            </div>
            <div className="h-64 animate-pulse rounded-2xl border border-white/[0.06] bg-[#0b1020]/90" />
        </div>
    );
}

function ProfileEmptyState({
    conversationHref,
    hasError,
}: {
    conversationHref: string;
    hasError: boolean;
}) {
    return (
        <section className="mt-12 flex min-h-[360px] flex-col items-center justify-center rounded-2xl border border-white/[0.08] bg-[#0b1020]/80 px-6 text-center">
            <span className="flex h-14 w-14 items-center justify-center rounded-full bg-blue-500/10 text-2xl">
                ◌
            </span>
            <h2 className="mt-6 text-xl font-medium text-slate-200">
                {hasError ? '生活模型暂时无法加载' : '还没有生成生活模型'}
            </h2>
            <p className="mt-3 max-w-md text-sm leading-6 text-slate-500">
                {hasError
                    ? '请稍后重试，或返回对话继续完善你的居住需求。'
                    : '先与 LiveOS 聊聊你的预算、通勤和生活偏好，我会在这里整理对你的理解。'}
            </p>
            <Link
                href={conversationHref}
                className="mt-7 rounded-xl bg-blue-500 px-6 py-3 text-sm font-medium text-white"
            >
                返回对话
            </Link>
        </section>
    );
}
