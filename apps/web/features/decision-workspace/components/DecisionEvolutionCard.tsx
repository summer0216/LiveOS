import { ArrowRight, RefreshCw, Scale } from 'lucide-react';
import type { ReactNode } from 'react';

import type {
  DecisionRecord,
  DecisionResult,
} from '@/services/decision';
import type { Property } from '@/services/property';

interface DecisionComparison {
  recommendationChanged: boolean;
  summaryChanged: boolean;
  confidenceDelta: number | null;
}

export function compareDecision(
  current: DecisionResult,
  previous: DecisionRecord,
): DecisionComparison {
  return {
    recommendationChanged:
      current.best_property_id !== previous.best_property_id,
    summaryChanged: current.summary !== previous.summary,
    confidenceDelta:
      current.confidence === null || previous.confidence === null
        ? null
        : current.confidence - previous.confidence,
  };
}

export function DecisionEvolutionCard({
  current,
  previous,
  properties,
  onRefresh,
}: {
  current: DecisionResult;
  previous: DecisionRecord | null;
  properties: Property[];
  onRefresh: () => void;
}) {
  return (
    <section
      aria-labelledby="decision-evolution-title"
      className="mt-8 rounded-2xl border border-white/[0.08] bg-[#0b1020]/90 p-6 shadow-[0_20px_60px_rgba(0,0,0,0.16)] sm:p-7"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-blue-500/20 bg-blue-500/10 text-blue-300">
            <Scale size={19} />
          </span>
          <div>
            <h2
              id="decision-evolution-title"
              className="font-medium text-slate-200"
            >
              Decision Evolution
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              当前 Decision 与上一次 Decision
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={onRefresh}
          className="flex items-center gap-2 rounded-xl border border-white/10 px-4 py-2 text-sm text-slate-400 transition hover:border-white/20 hover:text-slate-200"
        >
          <RefreshCw size={15} />
          Refresh Decision
        </button>
      </div>

      {previous === null ? (
        <p className="mt-6 rounded-xl border border-dashed border-white/[0.08] bg-black/10 px-5 py-6 text-sm text-slate-500">
          No previous decision.
        </p>
      ) : (
        <EvolutionDetails
          current={current}
          previous={previous}
          properties={properties}
        />
      )}
    </section>
  );
}

function EvolutionDetails({
  current,
  previous,
  properties,
}: {
  current: DecisionResult;
  previous: DecisionRecord;
  properties: Property[];
}) {
  const comparison = compareDecision(current, previous);
  const previousProperty = properties.find(
    (property) => property.id === previous.best_property_id,
  );
  const currentProperty = properties.find(
    (property) => property.id === current.best_property_id,
  );

  return (
    <div className="mt-6 grid gap-4 lg:grid-cols-3">
      <EvolutionMetric
        label="Recommendation"
        status={
          comparison.recommendationChanged
            ? 'Recommendation Updated'
            : 'Recommendation Stable'
        }
      >
        <ValueTransition
          previous={
            <>
              <span>
                {propertyLabel(
                  previousProperty,
                  previous.best_property_id,
                )}
              </span>
              {!previousProperty && (
                <span className="mt-1 block text-xs text-amber-300/80">
                  Currently unavailable
                </span>
              )}
            </>
          }
          current={propertyLabel(
            currentProperty,
            current.best_property_id,
          )}
        />
      </EvolutionMetric>

      <EvolutionMetric
        label="Summary"
        status={
          comparison.summaryChanged
            ? 'Summary Updated'
            : 'Summary Unchanged'
        }
      />

      <EvolutionMetric label="Confidence" status="Previous → Current">
        <ValueTransition
          previous={formatConfidence(previous.confidence)}
          current={formatConfidence(current.confidence)}
        />
        {comparison.confidenceDelta !== null && (
          <p className="mt-3 font-mono text-xs text-blue-300">
            {formatConfidenceDelta(comparison.confidenceDelta)}
          </p>
        )}
      </EvolutionMetric>
    </div>
  );
}

function EvolutionMetric({
  label,
  status,
  children,
}: {
  label: string;
  status: string;
  children?: ReactNode;
}) {
  return (
    <article className="rounded-xl border border-white/[0.06] bg-black/10 px-5 py-5">
      <p className="text-xs uppercase tracking-[0.14em] text-slate-600">
        {label}
      </p>
      <p className="mt-3 text-sm font-medium text-slate-300">{status}</p>
      {children}
    </article>
  );
}

function ValueTransition({
  previous,
  current,
}: {
  previous: ReactNode;
  current: ReactNode;
}) {
  return (
    <div className="mt-4 flex items-center gap-3 text-sm">
      <div className="min-w-0 flex-1">
        <p className="text-xs text-slate-600">Previous</p>
        <div className="mt-1 break-words text-slate-400">{previous}</div>
      </div>
      <ArrowRight className="shrink-0 text-slate-700" size={16} />
      <div className="min-w-0 flex-1">
        <p className="text-xs text-slate-600">Current</p>
        <div className="mt-1 break-words text-blue-300">{current}</div>
      </div>
    </div>
  );
}

function propertyLabel(
  property: Property | undefined,
  propertyId: string | null,
): string {
  return property?.title?.trim() || propertyId || 'Not provided';
}

function formatConfidence(confidence: number | null): string {
  return confidence === null
    ? 'Not provided'
    : `${Math.round(confidence * 100)}%`;
}

function formatConfidenceDelta(delta: number): string {
  const percentagePoints = Math.round(delta * 100);

  return `${percentagePoints > 0 ? '+' : ''}${percentagePoints} pts`;
}
