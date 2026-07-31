'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import {
  AlertTriangle,
  Check,
  Clock3,
  History,
  House,
  RefreshCw,
  Scale,
  Sparkles,
} from 'lucide-react';

import AICore, {
  type AICoreState,
} from '@/features/ai-entry/components/AICore';
import { PropertyCard } from '@/features/property-workspace';
import {
  getDecisionHistory,
  type DecisionHistoryResponse,
  type DecisionReason,
  type DecisionRecord,
  type DecisionTradeOff,
} from '@/services/decision';
import { getProperties, type Property } from '@/services/property';

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

const INVALID_TIME_LABEL = '时间信息不可用';

function formatCreatedAt(createdAt: string): string {
  const date = new Date(createdAt);

  if (Number.isNaN(date.getTime())) {
    return INVALID_TIME_LABEL;
  }

  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

function formatConfidence(confidence: number | null): string {
  if (confidence === null) {
    return '未提供';
  }

  const safeConfidence = Math.min(1, Math.max(0, confidence));

  return `${Math.round(safeConfidence * 100)}%`;
}

export default function HistoryWorkspace() {
  const searchParams = useSearchParams();
  const conversationId = searchParams.get('conversation_id') ?? '';
  const [history, setHistory] = useState<DecisionHistoryResponse | null>(null);
  const [properties, setProperties] = useState<Property[]>([]);
  const [isLoading, setIsLoading] = useState(Boolean(conversationId));
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(
    conversationId ? null : '缺少 conversation_id，无法加载决策历史。',
  );
  const [propertyError, setPropertyError] = useState(false);
  const [requestKey, setRequestKey] = useState(0);

  useEffect(() => {
    let isActive = true;
    const abortController = new AbortController();

    async function loadHistory() {
      if (!conversationId) {
        setError('缺少 conversation_id，无法加载决策历史。');
        setIsLoading(false);
        setIsRefreshing(false);
        return;
      }

      if (requestKey === 0) {
        setIsLoading(true);
      } else {
        setIsRefreshing(true);
      }

      setError(null);

      const [historyResult, propertyResult] = await Promise.allSettled([
        getDecisionHistory(conversationId, abortController.signal),
        getProperties(conversationId, abortController.signal),
      ]);

      if (!isActive) {
        return;
      }

      if (historyResult.status === 'rejected') {
        console.error(
          'Failed to load Decision History:',
          historyResult.reason,
        );
        setError('无法加载决策历史');
      } else {
        setHistory(historyResult.value);
      }

      if (propertyResult.status === 'rejected') {
        console.error(
          'Failed to load properties for Decision History:',
          propertyResult.reason,
        );
        setPropertyError(true);
        setProperties([]);
      } else {
        setPropertyError(false);
        setProperties(propertyResult.value);
      }

      setIsLoading(false);
      setIsRefreshing(false);
    }

    void loadHistory();

    return () => {
      isActive = false;
      abortController.abort();
    };
  }, [conversationId, requestKey]);

  const decisionHref = conversationId
    ? `/workspace/decision?conversation_id=${encodeURIComponent(conversationId)}`
    : '/workspace/decision';
  const memoryHref = conversationId
    ? `/workspace/memory?conversation_id=${encodeURIComponent(conversationId)}`
    : '/workspace/memory';

  return (
    <main className="min-h-screen bg-[#050812] text-slate-100">
      <WorkspaceHeader
        decisionHref={decisionHref}
        memoryHref={memoryHref}
        coreState={
          error
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
                DECISION HISTORY
              </p>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
                决策历史
              </h1>
              <p className="mt-3 max-w-xl text-base leading-7 text-slate-500">
                查看 AI 曾经为当前会话生成的居住决策。
              </p>
            </div>
            <button
              type="button"
              disabled={isLoading || isRefreshing || !conversationId}
              onClick={() => {
                setRequestKey((currentKey) => currentKey + 1);
              }}
              className="flex w-fit items-center gap-2 rounded-xl border border-blue-500/30 bg-blue-500/10 px-5 py-3 text-sm font-medium text-blue-300 transition hover:border-blue-400/50 hover:bg-blue-500/15 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <RefreshCw
                size={16}
                className={isRefreshing ? 'animate-spin' : undefined}
              />
              {isRefreshing ? '刷新中…' : '刷新'}
            </button>
          </section>

          <HistorySummary
            total={history?.total ?? null}
            isLoading={isLoading}
          />

          {isLoading && <HistoryLoading />}

          {!isLoading && error && history === null && (
            <HistoryError
              message={error}
              canRetry={Boolean(conversationId)}
              onRetry={() => {
                setRequestKey((currentKey) => currentKey + 1);
              }}
            />
          )}

          {!isLoading && error && history !== null && (
            <p
              role="alert"
              className="mt-6 rounded-xl border border-amber-400/20 bg-amber-400/5 px-4 py-3 text-sm text-amber-200"
            >
              刷新失败，当前仍显示上一次成功读取的历史。
            </p>
          )}

          {!isLoading && history?.items.length === 0 && (
            <HistoryEmptyState decisionHref={decisionHref} />
          )}

          {!isLoading && history && history.items.length > 0 && (
            <section aria-labelledby="history-list-title" className="mt-8">
              <h2
                id="history-list-title"
                className="text-lg font-medium text-slate-200"
              >
                History List
              </h2>
              <p className="mt-1 text-sm text-slate-600">
                最新生成的 Decision 显示在最上方
              </p>
              <div className="mt-5 grid gap-6">
                {history.items.map((record) => (
                  <DecisionRecordCard
                    key={record.id}
                    record={record}
                    property={properties.find(
                      (property) =>
                        property.id === record.best_property_id,
                    )}
                    propertyError={propertyError}
                  />
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
      <div className="mx-auto flex h-[72px] max-w-[1480px] items-center gap-8 px-5 sm:px-8">
        <Link
          href="/"
          aria-label="返回 LiveOS 首页"
          className="flex shrink-0 items-center gap-2.5"
        >
          <AICore state={coreState} size="runtime" />
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
            const isComplete = stepNumber < 8;
            const isCurrent = stepNumber === 8;
            const content = (
              <div className="flex items-center">
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
                    {isComplete ? <Check size={14} /> : stepNumber}
                  </span>
                  <span>{step}</span>
                </div>
                {index < JOURNEY_STEPS.length - 1 && (
                  <span className="mx-3 h-px w-5 bg-slate-800" />
                )}
              </div>
            );

            if (stepNumber === 7) {
              return (
                <Link
                  key={step}
                  href={decisionHref}
                  aria-label="返回 AI Decision"
                >
                  {content}
                </Link>
              );
            }

            if (stepNumber === 9) {
              return (
                <Link
                  key={step}
                  href={memoryHref}
                  aria-label="打开决策记忆"
                >
                  {content}
                </Link>
              );
            }

            return <div key={step}>{content}</div>;
          })}
        </nav>

        <Link
          href={memoryHref}
          className="ml-auto rounded-xl border border-white/10 px-4 py-2 text-sm text-slate-400 transition hover:border-white/20 hover:text-slate-200"
        >
          进入决策记忆
        </Link>
      </div>
    </header>
  );
}

function HistorySummary({
  total,
  isLoading,
}: {
  total: number | null;
  isLoading: boolean;
}) {
  return (
    <section className="mt-10 rounded-2xl border border-white/[0.08] bg-[#0b1020]/90 p-6 shadow-[0_20px_60px_rgba(0,0,0,0.2)] sm:p-7">
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-blue-500/20 bg-blue-500/10 text-blue-300">
          <History size={19} />
        </span>
        <div>
          <h2 className="font-medium text-slate-200">History Summary</h2>
          <p className="mt-1 text-sm text-slate-500">当前会话保存的决策记录</p>
        </div>
      </div>
      <div className="mt-6 rounded-xl border border-white/[0.06] bg-black/10 px-5 py-4">
        <p className="text-sm text-slate-500">历史记录</p>
        {isLoading ? (
          <div className="mt-3 h-8 w-20 animate-pulse rounded bg-white/[0.06]" />
        ) : (
          <p className="mt-2 font-mono text-3xl font-medium text-blue-400">
            {total ?? '无法读取'}
            {typeof total === 'number' && (
              <span className="ml-2 text-sm font-normal text-slate-600">
                条
              </span>
            )}
          </p>
        )}
      </div>
    </section>
  );
}

function HistoryLoading() {
  return (
    <section
      aria-live="polite"
      className="mt-8 rounded-2xl border border-white/[0.08] bg-[#0b1020]/90 p-6 sm:p-7"
    >
      <p className="text-sm text-slate-400">正在加载决策历史…</p>
      <div className="mt-5 h-72 animate-pulse rounded-xl bg-white/[0.04]" />
    </section>
  );
}

function HistoryEmptyState({ decisionHref }: { decisionHref: string }) {
  return (
    <section className="mt-8 flex min-h-72 flex-col items-center justify-center rounded-2xl border border-dashed border-white/[0.1] bg-[#0b1020]/70 px-6 text-center">
      <span className="flex h-14 w-14 items-center justify-center rounded-2xl border border-white/[0.08] bg-white/[0.03] text-slate-500">
        <History size={24} />
      </span>
      <h2 className="mt-6 text-lg font-medium text-slate-300">
        还没有决策记录
      </h2>
      <p className="mt-3 max-w-sm text-sm leading-6 text-slate-500">
        完成一次 AI 决策后，历史记录会显示在这里。
      </p>
      <Link
        href={decisionHref}
        className="mt-6 rounded-xl border border-blue-500/30 bg-blue-500/10 px-5 py-3 text-sm font-medium text-blue-300 transition hover:border-blue-400/50 hover:bg-blue-500/15"
      >
        前往 AI 决策
      </Link>
    </section>
  );
}

function HistoryError({
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
        无法加载决策历史
      </h2>
      <p className="mt-3 text-sm text-amber-200/70">{message}</p>
      {canRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-6 flex items-center gap-2 rounded-xl border border-blue-500/30 bg-blue-500/10 px-5 py-3 text-sm font-medium text-blue-300 transition hover:border-blue-400/50 hover:bg-blue-500/15"
        >
          <RefreshCw size={16} />
          重新加载
        </button>
      )}
    </section>
  );
}

function DecisionRecordCard({
  record,
  property,
  propertyError,
}: {
  record: DecisionRecord;
  property: Property | undefined;
  propertyError: boolean;
}) {
  return (
    <article className="rounded-2xl border border-white/[0.08] bg-[#0b1020]/90 p-6 shadow-[0_20px_60px_rgba(0,0,0,0.16)] sm:p-7">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
        <div>
          <p className="font-mono text-xs tracking-[0.12em] text-blue-400">
            DECISION RECORD
          </p>
          <h3 className="mt-3 text-xl font-medium leading-8 text-slate-200">
            {record.summary}
          </h3>
        </div>
        <div className="flex shrink-0 items-center gap-2 text-sm text-slate-500">
          <Clock3 size={15} />
          <time dateTime={record.created_at}>
            {formatCreatedAt(record.created_at)}
          </time>
        </div>
      </div>

      <section className="mt-6">
        <h4 className="text-sm font-medium text-slate-300">Best Property</h4>
        <div className="mt-3">
          {propertyError ? (
            <PropertyUnavailable
              propertyId={record.best_property_id}
              message="暂时无法读取当前房源信息"
            />
          ) : property ? (
            <PropertyCard property={property} />
          ) : (
            <PropertyUnavailable
              propertyId={record.best_property_id}
              message="该房源已不在当前房源列表中"
            />
          )}
        </div>
      </section>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <RecordItems
          title="推荐理由"
          emptyLabel="暂无推荐理由"
          items={record.reasons}
          icon="reasons"
        />
        <RecordItems
          title="需要权衡"
          emptyLabel="暂无明显权衡项"
          items={record.trade_offs}
          icon="trade-offs"
        />
      </div>

      <div className="mt-4 rounded-xl border border-white/[0.06] bg-black/10 px-5 py-4">
        <p className="text-sm text-slate-500">决策置信度</p>
        <p className="mt-2 font-mono text-2xl font-medium text-blue-400">
          {formatConfidence(record.confidence)}
        </p>
      </div>
    </article>
  );
}

function PropertyUnavailable({
  propertyId,
  message,
}: {
  propertyId: string;
  message: string;
}) {
  return (
    <div className="rounded-xl border border-dashed border-white/[0.1] bg-black/10 px-5 py-5">
      <div className="flex items-center gap-2 text-slate-400">
        <House size={17} />
        <p className="font-medium">历史推荐房源</p>
      </div>
      <p className="mt-3 text-sm text-slate-500">{message}</p>
      <p className="mt-2 break-all font-mono text-xs text-slate-600">
        Property ID: {propertyId}
      </p>
    </div>
  );
}

function RecordItems({
  title,
  emptyLabel,
  items,
  icon,
}: {
  title: string;
  emptyLabel: string;
  items: DecisionReason[] | DecisionTradeOff[];
  icon: 'reasons' | 'trade-offs';
}) {
  const Icon = icon === 'reasons' ? Sparkles : Scale;

  return (
    <section className="rounded-xl border border-white/[0.06] bg-black/10 px-5 py-5">
      <h4 className="flex items-center gap-2 text-sm font-medium text-slate-300">
        <Icon size={16} className="text-blue-300" />
        {title}
      </h4>
      {items.length === 0 ? (
        <p className="mt-4 text-sm text-slate-600">{emptyLabel}</p>
      ) : (
        <div className="mt-4 grid gap-3">
          {items.map((item) => (
            <div
              key={`${item.title}-${item.description}`}
              className="rounded-lg border border-white/[0.05] px-4 py-3"
            >
              <p className="text-sm font-medium text-slate-300">
                {item.title}
              </p>
              <p className="mt-2 text-sm leading-6 text-slate-500">
                {item.description}
              </p>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
