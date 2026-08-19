'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import {
  AlertTriangle,
  ArrowDown,
  Clock3,
  History,
  RefreshCw,
} from 'lucide-react';

import AICore, {
  type AICoreState,
} from '@/features/ai-entry/components/AICore';
import {
  getDecisionHistory,
  type DecisionHistoryResponse,
  type DecisionRecord,
} from '@/services/decision';

const NEXT_DELIMITER = '下一步：';

interface JourneyState {
  id: string;
  createdAt: string;
  decisionText: string;
  bestPropertyId: string;
  primaryTradeOff: string | null;
  primaryNextAction: string | null;
}

function normalized(value: string | null): string {
  return value?.replace(/\s+/g, '').trim() ?? '';
}

function decisionSignals(value: string): string {
  const normalizedValue = normalized(value).replace(/单人/g, '1人');
  const numbers = normalizedValue.match(/\d+(?:\.\d+)?/g) ?? [];
  const keywords = [
    '不可行',
    '可行',
    '不建议',
    '建议',
    '不适合',
    '适合',
    '不接受',
    '接受',
    '不优先',
    '优先',
  ].filter((keyword) => normalizedValue.includes(keyword));

  return [...numbers, ...keywords].join('|');
}

function parseSummary(summary: string) {
  const index = summary.indexOf(NEXT_DELIMITER);
  if (index === -1) return { decisionText: summary.trim(), nextAction: null };

  const candidate = summary.slice(index + NEXT_DELIMITER.length).trim();
  const isMultipleActions = /\n|(?:^|\s)[1-9][.、)]|[•·]/.test(candidate);
  return {
    decisionText: summary.slice(0, index).trim(),
    nextAction: candidate && !isMultipleActions ? candidate : null,
  };
}

function toJourneyState(record: DecisionRecord): JourneyState {
  const { decisionText, nextAction } = parseSummary(record.summary);
  const tradeOff = record.trade_offs[0];
  return {
    id: record.id,
    createdAt: record.created_at,
    decisionText,
    bestPropertyId: record.best_property_id,
    primaryTradeOff: tradeOff
      ? [tradeOff.title, tradeOff.description].filter(Boolean).join('：')
      : null,
    primaryNextAction: nextAction,
  };
}

function isSameState(left: JourneyState, right: JourneyState): boolean {
  const sameDecision =
    normalized(left.decisionText) === normalized(right.decisionText) ||
    decisionSignals(left.decisionText) === decisionSignals(right.decisionText);

  return (
    sameDecision &&
    left.bestPropertyId === right.bestPropertyId &&
    normalized(left.primaryTradeOff) === normalized(right.primaryTradeOff) &&
    normalized(left.primaryNextAction) === normalized(right.primaryNextAction)
  );
}

function buildJourney(
  records: DecisionRecord[],
  conversationId: string,
): JourneyState[] {
  const chronological = records
    .filter((record) => record.conversation_id === conversationId)
    .slice()
    .sort(
      (left, right) =>
        new Date(left.created_at).getTime() -
        new Date(right.created_at).getTime(),
    );

  return chronological.reduce<JourneyState[]>((states, record) => {
    const state = toJourneyState(record);
    const previous = states.at(-1);
    if (!previous || !isSameState(previous, state)) states.push(state);
    return states;
  }, []);
}

function formatCreatedAt(createdAt: string): string {
  const date = new Date(createdAt);
  if (Number.isNaN(date.getTime())) return '时间信息不可用';
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

export default function HistoryWorkspace() {
  const searchParams = useSearchParams();
  const conversationId = searchParams.get('conversation_id') ?? '';
  const [history, setHistory] = useState<DecisionHistoryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(Boolean(conversationId));
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(
    conversationId ? null : '缺少 conversation_id，无法加载决策旅程。',
  );
  const [requestKey, setRequestKey] = useState(0);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    async function load() {
      if (!conversationId) {
        setIsLoading(false);
        return;
      }
      if (requestKey === 0) {
        setIsLoading(true);
      } else {
        setIsRefreshing(true);
      }
      setError(null);
      try {
        const response = await getDecisionHistory(
          conversationId,
          controller.signal,
        );
        if (active) setHistory(response);
      } catch (loadError: unknown) {
        if (active) {
          console.error('Failed to load Decision Journey:', loadError);
          setError('无法加载决策旅程');
        }
      } finally {
        if (active) {
          setIsLoading(false);
          setIsRefreshing(false);
        }
      }
    }
    void load();
    return () => {
      active = false;
      controller.abort();
    };
  }, [conversationId, requestKey]);

  const scopedRecords = useMemo(
    () =>
      history?.items.filter(
        (record) => record.conversation_id === conversationId,
      ) ?? [],
    [conversationId, history],
  );
  const journey = useMemo(
    () => buildJourney(history?.items ?? [], conversationId),
    [conversationId, history],
  );
  const decisionHref = `/workspace/decision${conversationId ? `?conversation_id=${encodeURIComponent(conversationId)}` : ''}`;
  const memoryHref = `/workspace/memory${conversationId ? `?conversation_id=${encodeURIComponent(conversationId)}` : ''}`;

  return (
    <main className="min-h-screen bg-[#050812] text-slate-100">
      <WorkspaceHeader
        decisionHref={decisionHref}
        memoryHref={memoryHref}
        coreState={
          error ? 'error' : isLoading || isRefreshing ? 'thinking' : 'completed'
        }
      />
      <div className="runtime-flow min-h-[calc(100vh-72px)] bg-[radial-gradient(circle_at_top,rgba(68,82,164,0.12)_0,transparent_42%),radial-gradient(rgba(91,112,180,0.08)_1px,transparent_1px)] bg-[size:auto,28px_28px]">
        <div className="mx-auto w-full max-w-[900px] px-5 py-10 sm:px-8 lg:py-14">
          <section className="flex flex-col justify-between gap-6 sm:flex-row sm:items-end">
            <div>
              <p className="font-mono text-xs tracking-[0.16em] text-blue-400">
                DECISION JOURNEY
              </p>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
                决策旅程
              </h1>
              <p className="mt-3 max-w-xl text-base leading-7 text-slate-500">
                看见你的居住判断如何从过去走到现在。
              </p>
            </div>
            <button
              type="button"
              disabled={isLoading || isRefreshing || !conversationId}
              onClick={() => setRequestKey((key) => key + 1)}
              className="flex w-fit items-center gap-2 rounded-xl border border-blue-500/30 bg-blue-500/10 px-5 py-3 text-sm font-medium text-blue-300 transition hover:bg-blue-500/15 disabled:opacity-50"
            >
              <RefreshCw
                size={16}
                className={isRefreshing ? 'animate-spin' : undefined}
              />
              {isRefreshing ? '刷新中…' : '刷新'}
            </button>
          </section>

          {!isLoading && history && (
            <p className="mt-8 text-sm text-slate-600">
              当前对话 {scopedRecords.length} 条记录，整理为 {journey.length}{' '}
              个关键判断
            </p>
          )}
          {isLoading && <JourneyLoading />}
          {!isLoading && error && history === null && (
            <JourneyError
              message={error}
              canRetry={Boolean(conversationId)}
              onRetry={() => setRequestKey((key) => key + 1)}
            />
          )}
          {!isLoading && error && history !== null && (
            <p
              role="alert"
              className="mt-6 rounded-xl border border-amber-400/20 bg-amber-400/5 px-4 py-3 text-sm text-amber-200"
            >
              刷新失败，当前仍显示上一次成功读取的旅程。
            </p>
          )}
          {!isLoading && history && journey.length === 0 && (
            <JourneyEmptyState decisionHref={decisionHref} />
          )}
          {!isLoading && journey.length > 0 && (
            <section aria-label="居住决策演变" className="mt-8">
              {journey.map((state, index) => {
                const current = index === journey.length - 1;
                const label = current
                  ? 'CURRENT'
                  : index === 0
                    ? 'EARLIER'
                    : 'LATER';
                return (
                  <div key={state.id}>
                    <JourneyNode
                      state={state}
                      label={label}
                      isCurrent={current}
                    />
                    {!current && (
                      <div className="flex h-16 items-center pl-8 text-slate-700">
                        <ArrowDown size={20} aria-hidden="true" />
                      </div>
                    )}
                  </div>
                );
              })}
            </section>
          )}
        </div>
      </div>
    </main>
  );
}

function WorkspaceHeader({
  decisionHref,
  memoryHref,
  coreState,
}: {
  decisionHref: string;
  memoryHref: string;
  coreState: AICoreState;
}) {
  return (
    <header className="border-b border-white/[0.06] bg-[#050812]/95">
      <div className="mx-auto flex h-[72px] max-w-[1480px] items-center gap-6 px-5 sm:px-8">
        <Link
          href="/"
          aria-label="返回 LiveOS 首页"
          className="flex shrink-0 items-center gap-2.5"
        >
          <AICore state={coreState} size="sm" />
          <span className="text-lg font-semibold">
            Live<span className="text-blue-500">OS</span>
          </span>
        </Link>
        <nav
          aria-label="决策旅程导航"
          className="ml-auto flex items-center gap-5 text-sm"
        >
          <Link
            href={decisionHref}
            className="text-slate-400 transition hover:text-blue-300"
          >
            当前决策
          </Link>
          <span className="font-medium text-blue-300">决策旅程</span>
          <Link
            href={memoryHref}
            className="text-slate-500 transition hover:text-blue-300"
          >
            决策记忆
          </Link>
        </nav>
      </div>
    </header>
  );
}

function JourneyNode({
  state,
  label,
  isCurrent,
}: {
  state: JourneyState;
  label: 'EARLIER' | 'LATER' | 'CURRENT';
  isCurrent: boolean;
}) {
  return (
    <article
      className={[
        'rounded-2xl border p-6 sm:p-8',
        isCurrent
          ? 'border-blue-500/35 bg-[linear-gradient(145deg,rgba(22,33,70,0.96),rgba(11,16,32,0.98))] shadow-[0_24px_80px_rgba(30,64,175,0.16)]'
          : 'border-white/[0.08] bg-[#0b1020]/80',
      ].join(' ')}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p
          className={`font-mono text-xs tracking-[0.16em] ${isCurrent ? 'text-blue-300' : 'text-slate-500'}`}
        >
          {label}
        </p>
        <div className="flex items-center gap-2 text-xs text-slate-600">
          <Clock3 size={14} />
          <time dateTime={state.createdAt}>
            {formatCreatedAt(state.createdAt)}
          </time>
        </div>
      </div>
      <h2
        className={`mt-5 leading-8 font-medium ${isCurrent ? 'text-2xl text-slate-100' : 'text-xl text-slate-300'}`}
      >
        {state.decisionText}
      </h2>
      {(state.primaryTradeOff || state.primaryNextAction) && (
        <div className="mt-7 grid gap-6 border-t border-white/[0.07] pt-6 sm:grid-cols-2">
          {state.primaryTradeOff && (
            <JourneyDetail label="TRADE-OFF" value={state.primaryTradeOff} />
          )}
          {state.primaryNextAction && (
            <JourneyDetail label="NEXT" value={state.primaryNextAction} />
          )}
        </div>
      )}
    </article>
  );
}

function JourneyDetail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="font-mono text-xs tracking-[0.14em] text-blue-400">
        {label}
      </p>
      <p className="mt-2 text-sm leading-6 text-slate-400">{value}</p>
    </div>
  );
}

function JourneyLoading() {
  return (
    <section
      aria-live="polite"
      className="mt-8 rounded-2xl border border-white/[0.08] bg-[#0b1020]/90 p-7"
    >
      <p className="text-sm text-slate-400">正在整理决策旅程…</p>
      <div className="mt-5 h-64 animate-pulse rounded-xl bg-white/[0.04]" />
    </section>
  );
}

function JourneyEmptyState({ decisionHref }: { decisionHref: string }) {
  return (
    <section className="mt-8 flex min-h-72 flex-col items-center justify-center rounded-2xl border border-dashed border-white/[0.1] bg-[#0b1020]/70 px-6 text-center">
      <span className="flex h-14 w-14 items-center justify-center rounded-2xl border border-white/[0.08] bg-white/[0.03] text-slate-500">
        <History size={24} />
      </span>
      <h2 className="mt-6 text-lg font-medium text-slate-300">
        LiveOS 还没有形成可记录的居住判断
      </h2>
      <p className="mt-3 max-w-sm text-sm leading-6 text-slate-500">
        当当前对话形成有效判断后，它会出现在这里。
      </p>
      <Link
        href={decisionHref}
        className="mt-6 rounded-xl border border-blue-500/30 bg-blue-500/10 px-5 py-3 text-sm font-medium text-blue-300"
      >
        返回当前决策
      </Link>
    </section>
  );
}

function JourneyError({
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
      <h2 className="mt-5 text-lg font-medium text-amber-100">
        无法加载决策旅程
      </h2>
      <p className="mt-3 text-sm text-amber-200/70">{message}</p>
      {canRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-6 flex items-center gap-2 rounded-xl border border-blue-500/30 bg-blue-500/10 px-5 py-3 text-sm font-medium text-blue-300"
        >
          <RefreshCw size={16} />
          重新加载
        </button>
      )}
    </section>
  );
}
