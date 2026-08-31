import type { ReactNode } from 'react';
import Link from 'next/link';
import { Plus } from 'lucide-react';

import AICore, {
    type AICoreState,
} from '@/features/ai-entry/components/AICore';

interface ConversationLayoutProps {
    children: ReactNode;
    coreState: AICoreState;
}

export default function ConversationLayout({
    children,
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

                    <div className="ml-auto flex shrink-0 items-center gap-3">
                        <Link
                            href="/"
                            className="hidden items-center gap-1.5 rounded-xl border border-white/10 px-3 py-2 text-sm text-slate-400 transition hover:border-white/20 hover:text-slate-200 sm:flex"
                        >
                            <Plus size={15} />
                            新问题
                        </Link>
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
