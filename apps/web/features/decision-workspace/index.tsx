'use client';

import { useEffect, useState, type ReactNode } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import {
  ArrowRight,
  AlertTriangle,
  Building2,
  Check,
  CircleDotDashed,
  Gauge,
  RefreshCw,
  Scale,
  Sparkles,
} from 'lucide-react';

import AICore, {
  type AICoreState,
} from '@/features/ai-entry/components/AICore';
import { PropertyCard } from '@/features/property-workspace';
import { DecisionEvolutionCard } from '@/features/decision-workspace/components/DecisionEvolutionCard';
import {
  getDecision,
  getDecisionHistory,
  type DecisionRecord,
  type DecisionReason,
  type DecisionResult,
  type DecisionTradeOff,
} from '@/services/decision';
import { getProperties, type Property } from '@/services/property';

const JOURNEY_STEPS = [
  '入口',
  '对话',
  '生活模型',
  '工作台',
  '详情',
  '对比',
  '决策',
  '历史',
] as const;

const WAITING_SUMMARY = 'AI 正在等待足够的信息，完成最终分析。';

type WorkspaceStatus =
  | 'loading'
  | 'waiting'
  | 'ready'
  | 'error'
  | 'invalid-property'
  | 'missing-conversation';

function splitDecisionSummary(summary: string | null): {
  decision: string | null;
  recommendation: string | null;
} {
  if (!summary?.trim()) {
    return { decision: summary, recommendation: null };
  }

  const [decision, recommendation] = summary.split(' 下一步：', 2);
  return {
    decision: decision.trim(),
    recommendation: recommendation?.trim() || null,
  };
}

function getDecisionCoreState(status: WorkspaceStatus): AICoreState {
  if (status === 'loading') {
    return 'decision';
  }

  if (status === 'ready') {
    return 'completed';
  }

  if (status === 'error' || status === 'invalid-property') {
    return 'error';
  }

  return 'idle';
}

export default function DecisionWorkspace() {
  const searchParams = useSearchParams();
  const conversationId = searchParams.get('conversation_id') ?? '';
  const [status, setStatus] = useState<WorkspaceStatus>(
    conversationId ? 'loading' : 'missing-conversation',
  );
  const [decision, setDecision] = useState<DecisionResult | null>(null);
  const [properties, setProperties] = useState<Property[]>([]);
  const [bestProperty, setBestProperty] = useState<Property | null>(null);
  const [previousDecision, setPreviousDecision] =
    useState<DecisionRecord | null>(null);
  const [requestKey, setRequestKey] = useState(0);

  useEffect(() => {
    let isActive = true;

    async function loadDecision() {
      if (!conversationId) {
        setStatus('missing-conversation');
        setDecision(null);
        setProperties([]);
        setBestProperty(null);
        setPreviousDecision(null);
        return;
      }

      setStatus('loading');
      setDecision(null);
      setBestProperty(null);

      try {
        let nextPreviousDecision: DecisionRecord | null = null;

        try {
          const history = await getDecisionHistory(conversationId);
          nextPreviousDecision = history.items[0] ?? null;
        } catch (historyError: unknown) {
          console.error(
            'Failed to load Decision History for Evolution:',
            historyError,
          );
        }

        const [nextDecision, nextProperties] = await Promise.all([
          getDecision(conversationId),
          getProperties(conversationId),
        ]);

        if (!isActive) {
          return;
        }

        setDecision(nextDecision);
        setProperties(nextProperties);
        setPreviousDecision(nextPreviousDecision);

        if (nextDecision.status === 'waiting') {
          setStatus('waiting');
          return;
        }

        const nextBestProperty = nextProperties.find(
          (property) => property.id === nextDecision.best_property_id,
        );

        if (!nextBestProperty) {
          setStatus('invalid-property');
          return;
        }

        setBestProperty(nextBestProperty);
        setStatus('ready');
      } catch (error: unknown) {
        console.error('Failed to load AI Decision:', error);

        if (isActive) {
          setStatus('error');
          setDecision(null);
          setProperties([]);
          setBestProperty(null);
          setPreviousDecision(null);
        }
      }
    }

    void loadDecision();

    return () => {
      isActive = false;
    };
  }, [conversationId, requestKey]);

  const propertyHref = conversationId
    ? `/workspace/property?conversation_id=${encodeURIComponent(conversationId)}`
    : '/workspace/property';
  const historyHref = conversationId
    ? `/workspace/history?conversation_id=${encodeURIComponent(conversationId)}`
    : '/workspace/history';

  return (
    <DecisionWorkspaceView
      status={status}
      decision={decision}
      bestProperty={bestProperty}
      previousDecision={previousDecision}
      properties={properties}
      propertyCount={properties.length}
      propertyHref={propertyHref}
      historyHref={historyHref}
      onRetry={() => {
        setRequestKey((currentKey) => currentKey + 1);
      }}
    />
  );
}

function DecisionWorkspaceView({
  status,
  decision,
  bestProperty,
  previousDecision,
  properties,
  propertyCount,
  propertyHref,
  historyHref,
  onRetry,
}: {
  status: WorkspaceStatus;
  decision: DecisionResult | null;
  bestProperty: Property | null;
  previousDecision: DecisionRecord | null;
  properties: Property[];
  propertyCount: number;
  propertyHref: string;
  historyHref: string;
  onRetry: () => void;
}) {
  const isLoading = status === 'loading';
  const summarySections = splitDecisionSummary(decision?.summary ?? null);

  return (
    <main className="min-h-screen bg-[#050812] text-slate-100">
      <WorkspaceHeader
        propertyHref={propertyHref}
        historyHref={historyHref}
        coreState={getDecisionCoreState(status)}
      />

      <div className="runtime-flow min-h-[calc(100vh-72px)] bg-[radial-gradient(circle_at_top,rgba(68,82,164,0.12)_0,transparent_42%),radial-gradient(rgba(91,112,180,0.08)_1px,transparent_1px)] bg-[size:auto,28px_28px]">
        <div className="mx-auto w-full max-w-[1180px] px-5 py-10 sm:px-8 lg:py-14">
          <section>
            <p className="font-mono text-xs tracking-[0.16em] text-blue-400">
              AI DECISION
            </p>
            <h1 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
              AI 决策
            </h1>
            <p className="mt-3 max-w-xl text-base leading-7 text-slate-500">
              AI 正在综合生活模型与候选房源，生成最终居住建议。
            </p>
          </section>

          <DecisionOverview
            propertyCount={propertyCount}
            status={status}
          />
          <DecisionSummary
            status={status}
            summary={summarySections.decision}
          />

          {status === 'ready' && summarySections.recommendation && (
            <ActionableRecommendation
              recommendation={summarySections.recommendation}
            />
          )}

          {isLoading && <BestPropertyLoading />}

          {status === 'waiting' && <DecisionWaitingState />}

          {status === 'ready' && bestProperty && decision && (
            <>
              <BestProperty property={bestProperty} />
              {decision.reasons.length > 0 && (
                <RecommendationReasons reasons={decision.reasons} />
              )}
              {decision.trade_offs.length > 0 && (
                <DecisionTradeOffs tradeOffs={decision.trade_offs} />
              )}
              {decision.confidence !== null && (
                <DecisionConfidence confidence={decision.confidence} />
              )}
              <DecisionEvolutionCard
                current={decision}
                previous={previousDecision}
                properties={properties}
                onRefresh={onRetry}
              />
            </>
          )}

          {status === 'error' && (
            <DecisionError
              title="AI 决策加载失败。"
              description="请稍后重试。"
              onRetry={onRetry}
            />
          )}

          {status === 'invalid-property' && (
            <DecisionError
              title="AI 决策暂时无法展示。"
              description="请重新生成决策。"
              onRetry={onRetry}
            />
          )}

          {status === 'missing-conversation' && (
            <DecisionError
              title="对话不存在。"
              description="请从当前对话重新进入 AI 决策。"
            />
          )}
        </div>
      </div>
    </main>
  );
}

function WorkspaceHeader({
  propertyHref,
  historyHref,
  coreState,
}: {
  propertyHref: string;
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
            const isComplete = stepNumber < 7;
            const isCurrent = stepNumber === 7;

            const stepContent = (
              <div key={step} className="flex items-center">
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

            return stepNumber === 8 ? (
              <Link
                key={step}
                href={historyHref}
                aria-label="打开决策历史"
              >
                {stepContent}
              </Link>
            ) : (
              stepContent
            );
          })}
        </nav>

        <Link
          href={propertyHref}
          className="ml-auto rounded-xl border border-white/10 px-4 py-2 text-sm text-slate-400 transition hover:border-white/20 hover:text-slate-200"
        >
          返回房源工作台
        </Link>
      </div>
    </header>
  );
}

function DecisionOverview({
  propertyCount,
  status,
}: {
  propertyCount: number;
  status: WorkspaceStatus;
}) {
  const isLoading = status === 'loading';
  const statusLabel =
    status === 'ready'
      ? 'Ready'
      : status === 'waiting'
        ? 'Waiting'
        : status === 'error' || status === 'invalid-property'
          ? 'Error'
          : status === 'missing-conversation'
            ? 'Unavailable'
            : null;

  return (
    <section
      aria-labelledby="decision-overview-title"
      className="mt-10 rounded-2xl border border-white/[0.08] bg-[#0b1020]/90 p-6 shadow-[0_20px_60px_rgba(0,0,0,0.2)] sm:p-7"
    >
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-blue-500/20 bg-blue-500/10 text-blue-300">
          <Building2 size={19} />
        </span>
        <div>
          <h2
            id="decision-overview-title"
            className="font-medium text-slate-200"
          >
            决策概览
          </h2>
          <p className="mt-1 text-sm text-slate-500">当前决策状态</p>
        </div>
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <OverviewMetric
          label="候选房源"
          value={
            isLoading
              ? null
              : status === 'ready' || status === 'waiting'
                ? `${propertyCount} 套`
                : '无法读取'
          }
        />
        <OverviewMetric label="最佳推荐" value={statusLabel} />
      </div>
    </section>
  );
}

function OverviewMetric({
  label,
  value,
}: {
  label: string;
  value: string | null;
}) {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-black/10 px-5 py-4">
      <p className="text-sm text-slate-500">{label}</p>
      {value === null ? (
        <div className="mt-3 h-8 w-20 animate-pulse rounded bg-white/[0.06]" />
      ) : (
        <p className="mt-2 font-mono text-2xl font-medium text-blue-400">
          {value}
        </p>
      )}
    </div>
  );
}

function DecisionSummary({
  status,
  summary,
}: {
  status: WorkspaceStatus;
  summary: string | null;
}) {
  const isLoading = status === 'loading';
  const statusLabel =
    status === 'ready'
      ? 'Ready'
      : status === 'waiting'
        ? 'Waiting'
        : status === 'error' || status === 'invalid-property'
          ? 'Error'
          : 'Unavailable';

  return (
    <section
      aria-labelledby="decision-summary-title"
      className="mt-8 rounded-2xl border border-white/[0.08] bg-[#0b1020]/90 p-6 shadow-[0_20px_60px_rgba(0,0,0,0.16)] sm:p-7"
    >
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/[0.08] bg-white/[0.03] text-slate-400">
          <Scale size={19} />
        </span>
        <div>
          <h2
            id="decision-summary-title"
            className="font-medium text-slate-200"
          >
            决策摘要
          </h2>
          <p className="mt-1 text-sm text-slate-600">最终建议生成状态</p>
        </div>
      </div>

      <div className="mt-6 rounded-xl border border-white/[0.06] bg-black/10 px-5 py-5">
        <p className="text-sm text-slate-500">当前状态</p>
        {isLoading ? (
          <>
            <div className="mt-3 h-7 w-24 animate-pulse rounded bg-white/[0.06]" />
            <div className="mt-4 h-4 w-3/4 animate-pulse rounded bg-white/[0.04]" />
          </>
        ) : (
          <>
            <p className="mt-2 font-mono text-2xl font-medium text-blue-400">
              {statusLabel}
            </p>
            {(status === 'waiting' || status === 'ready') && (
              <p className="mt-3 text-sm leading-6 text-slate-500">
                {summary?.trim() || WAITING_SUMMARY}
              </p>
            )}
          </>
        )}
      </div>
    </section>
  );
}

function ActionableRecommendation({
  recommendation,
}: {
  recommendation: string;
}) {
  return (
    <section
      aria-labelledby="actionable-recommendation-title"
      className="mt-8 rounded-2xl border border-blue-500/20 bg-blue-500/[0.06] p-6 shadow-[0_20px_60px_rgba(0,0,0,0.12)] sm:p-7"
    >
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-blue-500/20 bg-blue-500/10 text-blue-300">
          <ArrowRight size={19} />
        </span>
        <div>
          <h2
            id="actionable-recommendation-title"
            className="font-medium text-slate-200"
          >
            下一步行动
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            基于当前决策与权衡的可执行建议
          </p>
        </div>
      </div>
      <p className="mt-6 rounded-xl border border-blue-500/10 bg-black/10 px-5 py-5 text-sm leading-7 text-slate-300">
        {recommendation}
      </p>
    </section>
  );
}

function BestPropertyLoading() {
  return (
    <section aria-label="最佳房源加载中" className="mt-8">
      <div className="h-6 w-36 animate-pulse rounded bg-white/[0.06]" />
      <div className="mt-5 h-80 animate-pulse rounded-2xl border border-white/[0.06] bg-[#0b1020]/90" />
    </section>
  );
}

function BestProperty({ property }: { property: Property }) {
  return (
    <section aria-labelledby="best-property-title" className="mt-8">
      <h2
        id="best-property-title"
        className="text-lg font-medium text-slate-200"
      >
        最佳房源
      </h2>
      <p className="mt-1 text-sm text-slate-600">
        当前决策选出的最佳房源
      </p>
      <div className="mt-5">
        <PropertyCard property={property} />
      </div>
    </section>
  );
}

function RecommendationReasons({ reasons }: { reasons: DecisionReason[] }) {
  return (
    <DecisionList
      title="推荐理由"
      description="AI 当前推荐这套房源的主要依据"
      items={reasons}
      icon={<Sparkles size={19} />}
    />
  );
}

function DecisionTradeOffs({
  tradeOffs,
}: {
  tradeOffs: DecisionTradeOff[];
}) {
  return (
    <DecisionList
      title="需要权衡"
      description="当前选择仍需留意的真实取舍"
      items={tradeOffs}
      icon={<Scale size={19} />}
    />
  );
}

function DecisionList({
  title,
  description,
  items,
  icon,
}: {
  title: string;
  description: string;
  items: Array<{ title: string; description: string }>;
  icon: ReactNode;
}) {
  return (
    <section className="mt-8 rounded-2xl border border-white/[0.08] bg-[#0b1020]/90 p-6 shadow-[0_20px_60px_rgba(0,0,0,0.16)] sm:p-7">
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-blue-500/20 bg-blue-500/10 text-blue-300">
          {icon}
        </span>
        <div>
          <h2 className="font-medium text-slate-200">{title}</h2>
          <p className="mt-1 text-sm text-slate-600">{description}</p>
        </div>
      </div>
      <div className="mt-6 grid gap-3">
        {items.map((item) => (
          <article
            key={`${item.title}-${item.description}`}
            className="rounded-xl border border-white/[0.06] bg-black/10 px-5 py-4"
          >
            <h3 className="text-sm font-medium text-slate-300">
              {item.title}
            </h3>
            <p className="mt-2 text-sm leading-6 text-slate-500">
              {item.description}
            </p>
          </article>
        ))}
      </div>
    </section>
  );
}

function DecisionConfidence({ confidence }: { confidence: number }) {
  return (
    <section className="mt-8 rounded-2xl border border-white/[0.08] bg-[#0b1020]/90 p-6 shadow-[0_20px_60px_rgba(0,0,0,0.16)] sm:p-7">
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-blue-500/20 bg-blue-500/10 text-blue-300">
          <Gauge size={19} />
        </span>
        <div>
          <h2 className="font-medium text-slate-200">可信度</h2>
          <p className="mt-1 text-sm text-slate-600">
            当前输入信息对决策的支持程度
          </p>
        </div>
      </div>
      <p className="mt-6 font-mono text-3xl font-medium text-blue-400">
        {Math.round(confidence * 100)}%
      </p>
    </section>
  );
}

function DecisionWaitingState() {
  return (
    <section className="mt-8 flex min-h-72 flex-col items-center justify-center rounded-2xl border border-dashed border-white/[0.1] bg-[#0b1020]/70 px-6 text-center">
      <span className="flex h-14 w-14 items-center justify-center rounded-2xl border border-white/[0.08] bg-white/[0.03] text-slate-500">
        <CircleDotDashed size={24} />
      </span>
      <h2 className="mt-6 text-lg font-medium text-slate-300">
        AI 还无法完成最终决策。
      </h2>
      <p className="mt-3 max-w-sm text-sm leading-6 text-slate-500">
        继续完善生活模型，并添加候选房源后，AI 将生成最佳居住建议。
      </p>
    </section>
  );
}

function DecisionError({
  title,
  description,
  onRetry,
}: {
  title: string;
  description: string;
  onRetry?: () => void;
}) {
  return (
    <section
      role="alert"
      className="mt-8 flex min-h-64 flex-col items-center justify-center rounded-2xl border border-dashed border-amber-400/20 bg-amber-400/[0.03] px-6 text-center"
    >
      <span className="flex h-14 w-14 items-center justify-center rounded-2xl border border-amber-400/20 bg-amber-400/5 text-amber-300">
        <AlertTriangle size={24} />
      </span>
      <h2 className="mt-6 text-lg font-medium text-amber-100">{title}</h2>
      <p className="mt-3 text-sm leading-6 text-amber-200/70">
        {description}
      </p>
      {onRetry && (
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
