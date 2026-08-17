import type { ReactNode } from 'react';
import Link from 'next/link';
import { Plus } from 'lucide-react';

import AICore, {
    type AICoreState,
} from '@/features/ai-entry/components/AICore';

interface ConversationLayoutProps {
    children: ReactNode;
    conversationId: string;
    coreState: AICoreState;
}

export default function ConversationLayout({
    children,
    conversationId,
    coreState,
}: ConversationLayoutProps) {
    const propertyHref = conversationId
        ? `/workspace/property?conversation_id=${encodeURIComponent(conversationId)}`
        : '/workspace/property';

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

                    <nav aria-label="LiveOS 主导航" className="hidden items-center gap-6 xl:flex">
                        <Link href={propertyHref} className="text-sm text-slate-400 transition hover:text-blue-400">
                            候选房源
                        </Link>
                        <span className="text-sm text-slate-600">决策旅程</span>
                    </nav>

                    <div className="ml-auto flex shrink-0 items-center gap-3">
                        <Link
                            href={conversationId ? `/conversation?conversation_id=${encodeURIComponent(conversationId)}` : '/conversation'}
                            className="hidden items-center gap-1.5 rounded-xl border border-white/10 px-3 py-2 text-sm text-slate-400 transition hover:border-white/20 hover:text-slate-200 sm:flex"
                        >
                            <Plus size={15} />
                            新对话
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
