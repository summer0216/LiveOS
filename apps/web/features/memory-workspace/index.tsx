'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import {
  AlertTriangle,
  Brain,
  Check,
  Clock3,
  Database,
  RefreshCw,
  Sparkles,
} from 'lucide-react';

import AICore, {
  type AICoreState,
} from '@/features/ai-entry/components/AICore';
import {
  getDecisionMemories,
  refreshDecisionMemories,
  type DecisionMemory,
  type DecisionMemoryRefreshResponse,
} from '@/services/memory';

const JOURNEY_STEPS = [
  '入口',
  '对话',
  '画像',
  '工作台',
  '详情',
  '对比',
  '决策',
  '历史',
  '记忆',
] as const;

type RefreshFeedback = {
  tone: 'success' | 'info' | 'error';
  message: string;
};

const CATEGORY_LABELS: Record<string, string> = {
  priority: '优先级',
  preference: '偏好',
  constraint: '约束',
  trade_off: '权衡',
};

export default function MemoryWorkspace() {
  const searchParams = useSearchParams();
  const conversationId = searchParams.get('conversation_id') ?? '';
  const [memories, setMemories] = useState<DecisionMemory[]>([]);
  const [isLoading, setIsLoading] = useState(Boolean(conversationId));
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(
    conversationId ? null : '缺少 conversation_id，无法加载决策记忆。',
  );
  const [refreshFeedback, setRefreshFeedback] =
    useState<RefreshFeedback | null>(null);
  const [requestKey, setRequestKey] = useState(0);

  useEffect(() => {
    let isActive = true;
    const abortController = new AbortController();

    async function loadMemories() {
      setRefreshFeedback(null);
      setMemories([]);

      if (!conversationId) {
        setIsLoading(false);
        setLoadError('缺少 conversation_id，无法加载决策记忆。');
        return;
      }

      setIsLoading(true);
      setLoadError(null);

      try {
        const response = await getDecisionMemories(
          conversationId,
          abortController.signal,
        );

        if (isActive) {
          setMemories(response.memories);
        }
      } catch (error: unknown) {
        console.error('Failed to load Decision Memories:', error);

        if (isActive) {
          setLoadError('无法加载决策记忆。');
        }
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    }

    void loadMemories();

    return () => {
      isActive = false;
      abortController.abort();
    };
  }, [conversationId, requestKey]);

  async function refreshMemories() {
    if (!conversationId || isRefreshing) {
      return;
    }

    setIsRefreshing(true);
    setRefreshFeedback(null);

    try {
      const refreshResult = await refreshDecisionMemories(conversationId);
      const listResult = await getDecisionMemories(conversationId);

      setMemories(listResult.memories);
      setLoadError(null);
      setRefreshFeedback(toRefreshFeedback(refreshResult));
    } catch (error: unknown) {
      console.error('Failed to refresh Decision Memories:', error);
      setRefreshFeedback({
        tone: 'error',
        message: '记忆刷新失败，已有记忆不受影响。',
      });
    } finally {
      setIsRefreshing(false);
    }
  }

  const historyHref = conversationId
    ? `/workspace/history?conversation_id=${encodeURIComponent(conversationId)}`
    : '/workspace/history';

  return (
    <main className="min-h-screen bg-[#050812] text-slate-100">
      <WorkspaceHeader
        historyHref={historyHref}
        coreState={
          loadError || refreshFeedback?.tone === 'error'
            ? 'error'
            : isLoading || isRefreshing
              ? 'thinking'
              : 'completed'
        }
      />

      <div className="runtime-flow min-h-[calc(100vh-72px)] bg-[radial-gradient(circle_at_top,rgba(68,82,164,0.12)_0,transparent_42%),radial-gradient(rgba(91,112,180,0.08)_1px,transparent_1px)] bg-[size:auto,28px_28px]">
        <div className="mx-auto w-full max-w-[1180px] px-5 py-10 sm:px-8 lg:py-14">
          <section className="flex flex-col justify-between gap-6 sm:flex-row sm:items-end">
            <div>
              <p className="font-mono text-xs tracking-[0.16em] text-blue-400">
                DECISION MEMORY
              </p>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
                决策记忆
              </h1>
              <p className="mt-3 max-w-xl text-base leading-7 text-slate-500">
                基于多次历史决策形成的长期偏好与权衡认知。
              </p>
            </div>
            <button
              type="button"
              disabled={
                isLoading || isRefreshing || !conversationId
              }
              onClick={() => {
                void refreshMemories();
              }}
              className="flex w-fit items-center gap-2 rounded-xl border border-blue-500/30 bg-blue-500/10 px-5 py-3 text-sm font-medium text-blue-300 transition hover:border-blue-400/50 hover:bg-blue-500/15 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <RefreshCw
                size={16}
                className={isRefreshing ? 'animate-spin' : undefined}
              />
              {isRefreshing ? 'Refreshing…' : 'Refresh Memory'}
            </button>
          </section>

          <MemorySummary
            count={isLoading || loadError ? null : memories.length}
          />

          {refreshFeedback && (
            <RefreshFeedbackMessage feedback={refreshFeedback} />
          )}

          {isLoading && <MemoryLoading />}

          {!isLoading && loadError && (
            <MemoryError
              message={loadError}
              canRetry={Boolean(conversationId)}
              onRetry={() => {
                setRequestKey((currentKey) => currentKey + 1);
              }}
            />
          )}

          {!isLoading && !loadError && memories.length === 0 && (
            <MemoryEmptyState
              isRefreshing={isRefreshing}
              onRefresh={() => {
                void refreshMemories();
              }}
            />
          )}

          {!isLoading && !loadError && memories.length > 0 && (
            <section aria-labelledby="memory-list-title" className="mt-8">
              <h2
                id="memory-list-title"
                className="text-lg font-medium text-slate-200"
              >
                Memory List
              </h2>
              <p className="mt-1 text-sm text-slate-600">
                最近更新的决策记忆显示在最上方
              </p>
              <div className="mt-5 grid gap-5 md:grid-cols-2">
                {memories.map((memory) => (
                  <MemoryCard key={memory.id} memory={memory} />
                ))}
              </div>
            </section>
          )}
        </div>
      </div>
    </main>
  );
}

function WorkspaceHeader({
  historyHref,
  coreState,
}: {
  historyHref: string;
  coreState: AICoreState;
}) {
  return (
    <header className="border-b border-white/[0.06] bg-[#050812]/95">
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
            const isComplete = stepNumber < 9;
            const isCurrent = stepNumber === 9;
            const content = (
              <div className="flex items-center">
                <div
                  className={[
                    'flex items-center gap-2 text-sm',
                    isCurrent
                      ? 'font-medium text-slate-100'
                      : 'text-blue-400',
                  ].join(' ')}
                >
                  <span
                    className={[
                      'flex h-7 w-7 items-center justify-center rounded-full border text-xs',
                      isCurrent
                        ? 'border-blue-500 bg-blue-500 text-white'
                        : 'border-blue-500/70 bg-blue-500/10',
                    ].join(' ')}
                  >
                    {isComplete ? <Check size={14} /> : stepNumber}
                  </span>
                  <span>{step}</span>
                </div>
                {index < JOURNEY_STEPS.length - 1 && (
                  <span className="mx-2 h-px w-4 bg-slate-800" />
                )}
              </div>
            );

            return stepNumber === 8 ? (
              <Link
                key={step}
                href={historyHref}
                aria-label="返回决策历史"
              >
                {content}
              </Link>
            ) : (
              <div key={step}>{content}</div>
            );
          })}
        </nav>

        <Link
          href={historyHref}
          className="ml-auto rounded-xl border border-white/10 px-4 py-2 text-sm text-slate-400 transition hover:border-white/20 hover:text-slate-200"
        >
          返回决策历史
        </Link>
      </div>
    </header>
  );
}

function MemorySummary({ count }: { count: number | null }) {
  return (
    <section className="mt-10 rounded-2xl border border-white/[0.08] bg-[#0b1020]/90 p-6 shadow-[0_20px_60px_rgba(0,0,0,0.2)] sm:p-7">
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-blue-500/20 bg-blue-500/10 text-blue-300">
          <Brain size={19} />
        </span>
        <div>
          <h2 className="font-medium text-slate-200">Memory Summary</h2>
          <p className="mt-1 text-sm text-slate-500">
            当前会话形成的稳定决策认知
          </p>
        </div>
      </div>
      <div className="mt-6 rounded-xl border border-white/[0.06] bg-black/10 px-5 py-4">
        <p className="text-sm text-slate-500">决策记忆</p>
        {count === null ? (
          <div className="mt-3 h-8 w-20 animate-pulse rounded bg-white/[0.06]" />
        ) : (
          <p className="mt-2 font-mono text-3xl font-medium text-blue-400">
            {count} 条
          </p>
        )}
      </div>
    </section>
  );
}

function MemoryLoading() {
  return (
    <section aria-label="决策记忆加载中" className="mt-8">
      <p className="text-sm text-slate-400">正在加载决策记忆…</p>
      <div className="mt-5 grid gap-5 md:grid-cols-2">
        {[0, 1].map((item) => (
          <div
            key={item}
            className="h-64 animate-pulse rounded-2xl border border-white/[0.06] bg-[#0b1020]/90"
          />
        ))}
      </div>
    </section>
  );
}

function MemoryEmptyState({
  isRefreshing,
  onRefresh,
}: {
  isRefreshing: boolean;
  onRefresh: () => void;
}) {
  return (
    <section className="mt-8 flex min-h-72 flex-col items-center justify-center rounded-2xl border border-dashed border-white/[0.1] bg-[#0b1020]/70 px-6 text-center">
      <span className="flex h-14 w-14 items-center justify-center rounded-2xl border border-white/[0.08] bg-white/[0.03] text-slate-500">
        <Database size={24} />
      </span>
      <h2 className="mt-6 text-lg font-medium text-slate-300">
        还没有形成决策记忆。
      </h2>
      <p className="mt-3 max-w-md text-sm leading-6 text-slate-500">
        完成至少两次决策后，可刷新并识别稳定的偏好与权衡模式。
      </p>
      <button
        type="button"
        disabled={isRefreshing}
        onClick={onRefresh}
        className="mt-6 flex items-center gap-2 rounded-xl border border-blue-500/30 bg-blue-500/10 px-5 py-3 text-sm font-medium text-blue-300 transition hover:border-blue-400/50 hover:bg-blue-500/15 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <RefreshCw
          size={16}
          className={isRefreshing ? 'animate-spin' : undefined}
        />
        {isRefreshing ? 'Refreshing…' : 'Refresh Memory'}
      </button>
    </section>
  );
}

function MemoryError({
  message,
  canRetry,
  onRetry,
}: {
  message: string;
  canRetry: boolean;
  onRetry: () => void;
}) {
  return (
    <section
      role="alert"
      className="mt-8 flex min-h-64 flex-col items-center justify-center rounded-2xl border border-dashed border-amber-400/20 bg-amber-400/[0.03] px-6 text-center"
    >
      <AlertTriangle size={24} className="text-amber-300" />
      <h2 className="mt-6 text-lg font-medium text-amber-100">
        无法加载决策记忆
      </h2>
      <p className="mt-3 text-sm text-amber-200/70">{message}</p>
      {canRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-6 flex items-center gap-2 rounded-xl border border-blue-500/30 bg-blue-500/10 px-5 py-3 text-sm font-medium text-blue-300 transition hover:border-blue-400/50 hover:bg-blue-500/15"
        >
          <RefreshCw size={16} />
          Retry
        </button>
      )}
    </section>
  );
}

function RefreshFeedbackMessage({
  feedback,
}: {
  feedback: RefreshFeedback;
}) {
  const toneClass =
    feedback.tone === 'error'
      ? 'border-amber-400/20 bg-amber-400/5 text-amber-200'
      : feedback.tone === 'success'
        ? 'border-emerald-400/20 bg-emerald-400/5 text-emerald-200'
        : 'border-blue-400/20 bg-blue-400/5 text-blue-200';

  return (
    <p
      role={feedback.tone === 'error' ? 'alert' : 'status'}
      className={`mt-6 rounded-xl border px-4 py-3 text-sm ${toneClass}`}
    >
      {feedback.message}
    </p>
  );
}

function MemoryCard({ memory }: { memory: DecisionMemory }) {
  return (
    <article className="rounded-2xl border border-white/[0.08] bg-[#0b1020]/90 p-6 shadow-[0_20px_60px_rgba(0,0,0,0.16)] sm:p-7">
      <div className="flex items-start justify-between gap-4">
        <span className="rounded-full border border-blue-500/20 bg-blue-500/10 px-3 py-1 font-mono text-xs text-blue-300">
          {CATEGORY_LABELS[memory.category] ?? memory.category}
        </span>
        <span className="font-mono text-xl font-medium text-blue-400">
          {formatConfidence(memory.confidence)}
        </span>
      </div>

      <p className="mt-6 text-base leading-7 text-slate-300">
        {memory.content}
      </p>

      <dl className="mt-6 grid gap-3 border-t border-white/[0.06] pt-5 sm:grid-cols-2">
        <div className="flex items-center gap-2 text-sm">
          <Sparkles size={15} className="text-slate-600" />
          <dt className="text-slate-600">决策证据</dt>
          <dd className="ml-auto text-slate-400">
            {memory.evidence_count} 条
          </dd>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <Clock3 size={15} className="text-slate-600" />
          <dt className="text-slate-600">最近更新</dt>
          <dd className="ml-auto text-right text-slate-400">
            {formatUpdatedAt(memory.updated_at)}
          </dd>
        </div>
      </dl>
    </article>
  );
}

function toRefreshFeedback(
  result: DecisionMemoryRefreshResponse,
): RefreshFeedback {
  if (result.status === 'failed') {
    return {
      tone: 'error',
      message: '记忆刷新失败，已有记忆不受影响。',
    };
  }

  if (result.status === 'insufficient_history') {
    return {
      tone: 'info',
      message: '需要至少两次决策记录，才能形成决策记忆。',
    };
  }

  if (result.saved_count === 0) {
    return {
      tone: 'info',
      message: '暂未发现新的稳定决策模式。',
    };
  }

  return {
    tone: 'success',
    message: `已处理 ${result.saved_count} 条记忆候选。`,
  };
}

function formatConfidence(confidence: number): string {
  const safeConfidence = Math.min(1, Math.max(0, confidence));

  return `${Math.round(safeConfidence * 100)}%`;
}

function formatUpdatedAt(updatedAt: string): string {
  const date = new Date(updatedAt);

  if (Number.isNaN(date.getTime())) {
    return '时间信息不可用';
  }

  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}
