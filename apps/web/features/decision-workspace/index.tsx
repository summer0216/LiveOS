'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { Building2, Check, CircleDotDashed, Scale } from 'lucide-react';

import { PropertyCard } from '@/features/property-workspace';
import { getProperty, type Property } from '@/services/property';

const JOURNEY_STEPS = [
  '入口',
  '对话',
  '画像',
  '工作台',
  '详情',
  '对比',
  '决策',
  '记忆',
] as const;

export default function DecisionWorkspace() {
  const searchParams = useSearchParams();
  const conversationId = searchParams.get('conversation_id') ?? '';
  const [propertyCount, setPropertyCount] = useState(0);
  const [isLoading, setIsLoading] = useState(Boolean(conversationId));
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    let isActive = true;

    async function loadPropertyCount() {
      if (!conversationId) {
        setIsLoading(false);
        return;
      }

      setIsLoading(true);
      setHasError(false);

      try {
        const property = await getProperty(conversationId);

        if (isActive) {
          setPropertyCount(property ? 1 : 0);
        }
      } catch (error: unknown) {
        console.error('Failed to load property for decision:', error);

        if (isActive) {
          setHasError(true);
          setPropertyCount(0);
        }
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    }

    void loadPropertyCount();

    return () => {
      isActive = false;
    };
  }, [conversationId]);

  const propertyHref = conversationId
    ? `/workspace/property?conversation_id=${encodeURIComponent(conversationId)}`
    : '/workspace/property';

  return (
    <DecisionWorkspaceView
      bestProperty={null}
      propertyCount={propertyCount}
      isLoading={isLoading}
      hasError={hasError}
      propertyHref={propertyHref}
    />
  );
}

function DecisionWorkspaceView({
  bestProperty,
  propertyCount,
  isLoading,
  hasError,
  propertyHref,
}: {
  bestProperty: Property | null;
  propertyCount: number;
  isLoading: boolean;
  hasError: boolean;
  propertyHref: string;
}) {
  const isReady = bestProperty !== null;

  return (
    <main className="min-h-screen bg-[#050812] text-slate-100">
      <WorkspaceHeader propertyHref={propertyHref} />

      <div className="min-h-[calc(100vh-72px)] bg-[radial-gradient(circle_at_top,rgba(68,82,164,0.12)_0,transparent_42%),radial-gradient(rgba(91,112,180,0.08)_1px,transparent_1px)] bg-[size:auto,28px_28px]">
        <div className="mx-auto w-full max-w-[1180px] px-5 py-10 sm:px-8 lg:py-14">
          <section>
            <p className="font-mono text-xs tracking-[0.16em] text-blue-400">
              AI DECISION
            </p>
            <h1 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
              AI Decision
            </h1>
            <p className="mt-3 max-w-xl text-base leading-7 text-slate-500">
              AI 正在综合 Living Profile 与候选房源，生成最终居住建议。
            </p>
          </section>

          {hasError && (
            <p
              role="alert"
              className="mt-6 rounded-xl border border-amber-400/20 bg-amber-400/5 px-4 py-3 text-sm text-amber-200"
            >
              Decision Workspace 暂时无法加载候选房源状态。
            </p>
          )}

          <DecisionOverview
            propertyCount={propertyCount}
            isReady={isReady}
            isLoading={isLoading}
          />
          <DecisionSummary isReady={isReady} isLoading={isLoading} />

          {!isLoading &&
            (bestProperty ? (
              <section aria-labelledby="best-property-title" className="mt-8">
                <div>
                  <h2
                    id="best-property-title"
                    className="text-lg font-medium text-slate-200"
                  >
                    Best Property
                  </h2>
                  <p className="mt-1 text-sm text-slate-600">
                    当前 Decision 选出的最佳房源
                  </p>
                </div>
                <div className="mt-5">
                  <PropertyCard property={bestProperty} />
                </div>
              </section>
            ) : (
              <DecisionWaitingState />
            ))}
        </div>
      </div>
    </main>
  );
}

function WorkspaceHeader({ propertyHref }: { propertyHref: string }) {
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

            return (
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
          })}
        </nav>

        <Link
          href={propertyHref}
          className="ml-auto rounded-xl border border-white/10 px-4 py-2 text-sm text-slate-400 transition hover:border-white/20 hover:text-slate-200"
        >
          返回 Property Workspace
        </Link>
      </div>
    </header>
  );
}

function DecisionOverview({
  propertyCount,
  isReady,
  isLoading,
}: {
  propertyCount: number;
  isReady: boolean;
  isLoading: boolean;
}) {
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
            Overview
          </h2>
          <p className="mt-1 text-sm text-slate-500">当前决策状态</p>
        </div>
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <OverviewMetric
          label="候选房源"
          value={isLoading ? null : `${propertyCount} 套`}
        />
        <OverviewMetric
          label="最佳推荐"
          value={isLoading ? null : isReady ? 'Ready' : 'Waiting'}
          tone={isReady ? 'blue' : 'slate'}
        />
      </div>
    </section>
  );
}

function OverviewMetric({
  label,
  value,
  tone = 'blue',
}: {
  label: string;
  value: string | null;
  tone?: 'blue' | 'slate';
}) {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-black/10 px-5 py-4">
      <p className="text-sm text-slate-500">{label}</p>
      {value === null ? (
        <div className="mt-3 h-8 w-20 animate-pulse rounded bg-white/[0.06]" />
      ) : (
        <p
          className={[
            'mt-2 font-mono text-2xl font-medium',
            tone === 'blue' ? 'text-blue-400' : 'text-slate-300',
          ].join(' ')}
        >
          {value}
        </p>
      )}
    </div>
  );
}

function DecisionSummary({
  isReady,
  isLoading,
}: {
  isReady: boolean;
  isLoading: boolean;
}) {
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
            Decision Summary
          </h2>
          <p className="mt-1 text-sm text-slate-600">最终建议生成状态</p>
        </div>
      </div>

      <div className="mt-6 rounded-xl border border-white/[0.06] bg-black/10 px-5 py-5">
        <p className="text-sm text-slate-500">当前状态</p>
        {isLoading ? (
          <div className="mt-3 h-7 w-24 animate-pulse rounded bg-white/[0.06]" />
        ) : (
          <>
            <p
              className={[
                'mt-2 font-mono text-2xl font-medium',
                isReady ? 'text-blue-400' : 'text-slate-300',
              ].join(' ')}
            >
              {isReady ? 'Ready' : 'Waiting'}
            </p>
            <p className="mt-3 text-sm leading-6 text-slate-500">
              {isReady
                ? 'AI 已完成当前候选房源分析。'
                : 'AI 正在等待足够的信息，完成最终分析。'}
            </p>
          </>
        )}
      </div>
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
        继续完善 Living Profile，并添加候选房源后，AI 将生成最佳居住建议。
      </p>
    </section>
  );
}
