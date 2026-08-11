import type { ReactNode } from 'react';
import Link from 'next/link';
import { Check } from 'lucide-react';

import AICore, {
    type AICoreState,
} from '@/features/ai-entry/components/AICore';

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

interface ConversationLayoutProps {
    children: ReactNode;
    profileHref: string;
    profileReady: boolean;
    coreState: AICoreState;
}

export default function ConversationLayout({
    children,
    profileHref,
    profileReady,
    coreState,
}: ConversationLayoutProps) {
    return (
        <main className="flex h-screen flex-col overflow-hidden bg-[#050812] text-slate-100">
            <header className="shrink-0 border-b border-white/[0.06] bg-[#050812]/95">
                <div className="mx-auto flex h-[72px] max-w-[1480px] items-center gap-8 px-5 sm:px-8">
                    <Link
                        href="/"
                        aria-label="返回 LiveOS 首页"
                        className="flex shrink-0 items-center gap-2.5"
                    >
                        <AICore state={coreState} size="sm" />
                        <span className="text-lg font-semibold tracking-tight">
                            Live
                            <span className="text-blue-500">OS</span>
                        </span>
                    </Link>

                    <nav
                        aria-label="LiveOS 决策旅程"
                        className="hidden min-w-0 flex-1 items-center justify-center xl:flex"
                    >
                        {JOURNEY_STEPS.map((step, index) => {
                            const stepNumber = index + 1;
                            const isComplete = stepNumber < 2;
                            const isCurrent = stepNumber === 2;
                            const isProfileStep = stepNumber === 3;

                            const content = (
                                <>
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
                                </>
                            );

                            return (
                                <div
                                    key={step}
                                    className="flex items-center"
                                >
                                    {isProfileStep && profileReady ? (
                                        <Link
                                            href={profileHref}
                                            className="flex items-center gap-2 text-sm text-slate-500 transition hover:text-blue-400"
                                        >
                                            {content}
                                        </Link>
                                    ) : (
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
                                            {content}
                                        </div>
                                    )}

                                    {index <
                                        JOURNEY_STEPS.length - 1 && (
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

            <div className="runtime-flow min-h-0 flex-1">{children}</div>
        </main>
    );
}
