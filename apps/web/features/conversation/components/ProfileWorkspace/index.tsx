import Link from 'next/link';
import {
    ArrowRight,
    Building2,
    CheckCircle2,
    Clock3,
    Circle,
    MapPin,
    PawPrint,
    Users,
    WalletCards,
    type LucideIcon,
} from 'lucide-react';

import type { LivingProfile } from '@/services/profile';

interface ProfileWorkspaceProps {
    profile: LivingProfile | null;
    isLoading: boolean;
    profileHref: string;
}

interface ProfileFieldItem {
    key: string;
    label: string;
    value: string | null;
    isIdentified: boolean;
    icon: LucideIcon;
}

function hasText(
    value: string | null | undefined,
): value is string {
    return typeof value === 'string' && value.trim().length > 0;
}

function getProfileFieldItems(
    profile: LivingProfile | null,
): ProfileFieldItem[] {
    const rawWorkLocation = profile?.work_location;
    const rawPreferredCity = profile?.preferred_city;
    const workLocation = hasText(rawWorkLocation)
        ? rawWorkLocation.trim()
        : null;
    const preferredCity = hasText(rawPreferredCity)
        ? rawPreferredCity.trim()
        : null;
    const hasBudget = typeof profile?.budget === 'number';
    const hasCommute =
        typeof profile?.commute_minutes === 'number';
    const hasFamilySize =
        typeof profile?.family_size === 'number';
    const hasPet = profile?.has_pet != null;

    return [
        {
            key: 'work_location',
            label: '工作地点',
            value: workLocation,
            isIdentified: workLocation !== null,
            icon: MapPin,
        },
        {
            key: 'budget',
            label: '预算',
            value: hasBudget
                ? `¥${profile.budget?.toLocaleString('zh-CN')} / 月`
                : null,
            isIdentified: hasBudget,
            icon: WalletCards,
        },
        {
            key: 'commute_minutes',
            label: '通勤要求',
            value: hasCommute
                ? `${profile.commute_minutes} 分钟以内`
                : null,
            isIdentified: hasCommute,
            icon: Clock3,
        },
        {
            key: 'preferred_city',
            label: '意向城市',
            value: preferredCity,
            isIdentified: preferredCity !== null,
            icon: Building2,
        },
        {
            key: 'family_size',
            label: '居住人数',
            value: hasFamilySize
                ? `${profile.family_size} 人`
                : null,
            isIdentified: hasFamilySize,
            icon: Users,
        },
        {
            key: 'has_pet',
            label: '宠物情况',
            value:
                profile?.has_pet == null
                    ? null
                    : profile.has_pet
                      ? '有宠物'
                      : '无宠物',
            isIdentified: hasPet,
            icon: PawPrint,
        },
    ];
}

export default function ProfileWorkspace({
    profile,
    isLoading,
    profileHref,
}: ProfileWorkspaceProps) {
    const items = getProfileFieldItems(profile);
    const identifiedItems = items.filter(
        (item) => item.isIdentified,
    );
    const unknownItems = items.filter(
        (item) => !item.isIdentified,
    );

    return (
        <aside className="flex h-full min-h-0 flex-col border-l border-white/[0.06] bg-[#060a14]">
            <div className="min-h-0 flex-1 overflow-y-auto px-6 py-7">
                <div className="flex items-center justify-between gap-4">
                    <h2 className="text-lg font-medium tracking-tight text-slate-100">
                        生活模型
                    </h2>
                    <span
                        aria-live="polite"
                        className={[
                            'flex min-w-[68px] items-center justify-end gap-1.5 font-mono text-[10px]',
                            isLoading
                                ? 'text-violet-400'
                                : profile
                                  ? 'text-blue-400'
                                  : 'text-slate-700',
                        ].join(' ')}
                    >
                        <span
                            className={[
                                'h-1.5 w-1.5 rounded-full',
                                isLoading
                                    ? 'animate-pulse bg-violet-400'
                                    : profile
                                      ? 'bg-blue-400'
                                      : 'bg-slate-800',
                            ].join(' ')}
                        />
                        {isLoading
                            ? '同步中'
                            : profile
                              ? '已同步'
                              : '等待信息'}
                    </span>
                </div>
                <p className="mt-2 text-sm leading-6 text-slate-600">
                    AI 正在根据对话持续理解你的居住需求
                </p>

                <div
                    aria-busy={isLoading}
                    className="mt-6 divide-y divide-white/[0.06] border-y border-white/[0.06]"
                >
                    {identifiedItems.map((item) => (
                        <ProfileFieldRow
                            key={item.key}
                            item={item}
                        />
                    ))}
                    {identifiedItems.length === 0 && (
                        <p className="py-5 text-sm leading-6 text-slate-700">
                            对话中识别到的信息会逐步出现在这里。
                        </p>
                    )}
                </div>

                <section className="mt-6 rounded-xl border border-white/[0.08] bg-[#0b1020] p-5">
                    <h3 className="font-mono text-xs tracking-[0.12em] text-blue-400">
                        AI 洞察
                    </h3>

                    <div className="mt-4 space-y-5">
                        {identifiedItems.length > 0 && (
                            <InsightGroup
                                title="已识别"
                                items={identifiedItems}
                                identified
                            />
                        )}

                        {unknownItems.length > 0 && (
                            <InsightGroup
                                title="仍需了解"
                                items={unknownItems}
                                identified={false}
                            />
                        )}
                    </div>
                </section>
            </div>

            <div className="shrink-0 border-t border-white/[0.06] bg-[#060a14]/95 p-6">
                {profile ? (
                    <Link
                        href={profileHref}
                        className="flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-blue-500 text-sm font-medium text-white shadow-[0_10px_30px_rgba(59,105,255,0.22)] transition hover:bg-blue-400"
                    >
                        查看生活模型
                        <ArrowRight size={16} />
                    </Link>
                ) : (
                    <button
                        type="button"
                        disabled
                        className="h-12 w-full cursor-not-allowed rounded-xl bg-slate-900 text-sm text-slate-700"
                    >
                        生活模型生成中
                    </button>
                )}
            </div>
        </aside>
    );
}

function InsightGroup({
    title,
    items,
    identified,
}: {
    title: string;
    items: ProfileFieldItem[];
    identified: boolean;
}) {
    return (
        <div>
            <p className="text-[10px] font-medium tracking-[0.14em] text-slate-700">
                {title}
            </p>
            <ul className="mt-2 space-y-2">
                {items.map((item) => (
                    <li
                        key={item.key}
                        className={[
                            'flex items-center gap-2 text-xs',
                            identified
                                ? 'text-slate-400'
                                : 'text-slate-600',
                        ].join(' ')}
                    >
                        {identified ? (
                            <CheckCircle2
                                size={14}
                                className="shrink-0 text-blue-400"
                            />
                        ) : (
                            <Circle
                                size={14}
                                className="shrink-0 text-slate-700"
                            />
                        )}
                        <span>
                            {identified
                                ? `已识别${item.label}`
                                : `仍需了解${item.label}`}
                        </span>
                    </li>
                ))}
            </ul>
        </div>
    );
}

function ProfileFieldRow({
    item,
}: {
    item: ProfileFieldItem;
}) {
    const Icon = item.icon;

    return (
        <div className="runtime-grow flex items-center gap-3 py-4">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-white/[0.08] bg-white/[0.03] text-blue-400">
                <Icon size={17} />
            </span>

            <div className="min-w-0 flex-1">
                <p className="text-xs text-slate-600">
                    {item.label}
                </p>
                <p
                    className={[
                        'mt-1 truncate text-sm',
                        item.value
                            ? 'text-slate-300'
                            : 'text-slate-700',
                    ].join(' ')}
                >
                    {item.value ?? '待了解'}
                </p>
            </div>
        </div>
    );
}
