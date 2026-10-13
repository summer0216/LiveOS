'use client';

import type { ChangeEvent, KeyboardEvent, ReactNode } from 'react';
import { useEffect, useRef, useState } from 'react';

import styles from './FirstOpen.module.css';

import type { FirstOpenRuntimeStage, WorldRevealPresentation } from '@/lib/runtimePresentationContract';

interface FirstOpenExperienceProps extends WorldRevealPresentation<HTMLSpanElement> {
  stage: FirstOpenRuntimeStage;
  worldFormed?: boolean;
  isSubmittingExpression?: boolean;
  submittedExpression: string | null;
  groundedIdentity: string | null;
  expressionReferent?: string | null;
  map?: ReactNode;
  worldProjection?: ReactNode;
  onSubmit: (expression: string) => void | Promise<void>;
}

type EntryFrame = 'idle' | 'focus' | 'typing' | 'ready';
type VisualFrame = EntryFrame | 'transmitting' | 'grounding' | 'world';

const READY_DELAY_MS = 460;
const WORLD_SETTLE_MS = 3200;

export const FIRST_OPEN_WORLD_CAMERA_TRANSITION_MS = 2800;

function ReturnMark() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M19 5v7.5a3 3 0 0 1-3 3H6m4-4-4 4 4 4" />
    </svg>
  );
}

export default function FirstOpenExperience({
  stage,
  worldFormed = false,
  isSubmittingExpression = false,
  groundedIdentity,
  expressionReferent = null,
  placeAnchorRef,
  map,
  worldProjection,
  onSubmit,
  onWorldSettled,
}: FirstOpenExperienceProps) {
  const [value, setValue] = useState('');
  const [entryFrame, setEntryFrame] = useState<EntryFrame>('idle');
  const [entryPending, setEntryPending] = useState(false);
  const entrySubmittingRef = useRef(false);
  const entrySubmitIdRef = useRef(0);
  const worldEntry = stage === 'world';
  const entryEditable = stage === 'entry' || worldEntry;
  const entryHidden = stage === 'submitting' || stage === 'grounding'
    || (stage === 'entry' && entryPending);

  useEffect(() => {
    if (!worldFormed || isSubmittingExpression) return;
    // Runtime readiness releases entry ownership while reply streaming continues.
    entrySubmitIdRef.current += 1;
    entrySubmittingRef.current = false;
  }, [worldFormed, isSubmittingExpression]);

  useEffect(() => {
    if (!entryEditable || !value.trim() || entryFrame !== 'typing') return;
    const timer = window.setTimeout(() => setEntryFrame('ready'), READY_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [entryEditable, entryFrame, value]);

  const visualFrame: VisualFrame = stage === 'world'
    ? 'world'
    : stage === 'grounding'
      ? 'grounding'
      : stage === 'submitting'
        ? 'transmitting'
        : entryFrame;

  useEffect(() => {
    if (visualFrame !== 'world' || worldFormed) return;
    const timer = window.setTimeout(() => {
      onWorldSettled();
    }, WORLD_SETTLE_MS);
    return () => window.clearTimeout(timer);
  }, [onWorldSettled, visualFrame, worldFormed]);

  const subjectIdentity = groundedIdentity ?? expressionReferent;
  const cameraAnchorMounted = Boolean(subjectIdentity && (
    stage === 'grounding' || stage === 'world'
  ));

  const handleChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
    const nextValue = event.target.value;
    setValue(nextValue);
    setEntryFrame(nextValue.trim() ? 'typing' : 'focus');
  };

  const submit = async () => {
    const nextExpression = value.trim();
    if (!nextExpression || !entryEditable || isSubmittingExpression || entrySubmittingRef.current
      || (worldEntry && !worldFormed)) return;

    entrySubmittingRef.current = true;
    const entrySubmitId = ++entrySubmitIdRef.current;
    setEntryPending(true);
    setValue('');
    if (worldFormed) {
      try {
        await onSubmit(nextExpression);
        if (entrySubmitIdRef.current === entrySubmitId) setEntryFrame('ready');
      } finally {
        if (entrySubmitIdRef.current === entrySubmitId) {
          entrySubmittingRef.current = false;
          setEntryPending(false);
        }
      }
      return;
    }

    setEntryFrame('ready');
    try {
      await onSubmit(nextExpression);
    } finally {
      if (entrySubmitIdRef.current === entrySubmitId) {
        entrySubmittingRef.current = false;
        setEntryPending(false);
      }
    }
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== 'Enter' || event.shiftKey) return;
    event.preventDefault();
    void submit();
  };

  return (
    <section
      className={styles.firstOpen}
      data-frame={visualFrame}
      data-world-entry={worldEntry || undefined}
      data-entry-frame={worldEntry
        ? isSubmittingExpression ? 'transmitting' : entryFrame
        : undefined}
      aria-label="LiveOS First Open"
    >
      {map && (
        <div className={styles.mapCanvas}>
          {map}
          {worldProjection}
        </div>
      )}

      <header className={styles.topbar}>
        <span className={styles.wordmark}>LiveOS</span>
        <span className={styles.account} aria-hidden="true"><span /></span>
      </header>

      <div className={styles.entryStage}>
        <div className={styles.conversationEntry}>
          <div className={styles.writingLine}>
            {cameraAnchorMounted && (
              <div className={styles.expressionGrounded} aria-hidden="true">
                <span ref={placeAnchorRef} className={styles.exprPlace}>
                  <span className={styles.placeLabel}>{subjectIdentity}</span>
                </span>
              </div>
            )}
            <div className={styles.expressionEntry} data-anchor-layout={cameraAnchorMounted} data-entry-hidden={entryHidden}>
              <textarea
                rows={1}
                value={value}
                readOnly={!entryEditable}
                aria-busy={isSubmittingExpression}
                tabIndex={entryEditable ? 0 : -1}
                onChange={handleChange}
                onFocus={() => {
                  if (entryEditable && !value.trim()) setEntryFrame('focus');
                }}
                onBlur={() => {
                  if (!entryEditable) return;
                  setEntryFrame(value.trim() ? 'ready' : 'idle');
                }}
                onKeyDown={handleKeyDown}
                placeholder="告诉 LiveOS…"
                aria-label="告诉 LiveOS 一件关于生活的事"
              />
              <button
                type="button"
                className={styles.commitMark}
                aria-label="提交表达"
                disabled={!entryEditable || !value.trim() || isSubmittingExpression || (worldEntry && !worldFormed)}
                onClick={() => { void submit(); }}
              >
                <ReturnMark />
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
