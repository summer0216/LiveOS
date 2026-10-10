'use client';

import type { ChangeEvent, KeyboardEvent, ReactNode, RefObject } from 'react';
import { useEffect, useMemo, useRef, useState } from 'react';

import styles from './FirstOpen.module.css';

export type FirstOpenRuntimeStage =
  | 'entry'
  | 'submitting'
  | 'grounding'
  | 'world';

interface FirstOpenExperienceProps {
  stage: FirstOpenRuntimeStage;
  submittedExpression: string | null;
  groundedIdentity: string | null;
  expressionReferent?: string | null;
  placeAnchorRef: RefObject<HTMLSpanElement | null>;
  map?: ReactNode;
  worldProjection?: ReactNode;
  onSubmit: (expression: string) => void;
  onGroundingSettled: () => void;
  onWorldSettled: () => void;
}

type EntryFrame = 'idle' | 'focus' | 'typing' | 'ready';
type VisualFrame = EntryFrame | 'transmitting' | 'grounding' | 'world';

const READY_DELAY_MS = 460;
const TRANSMISSION_MS = 1100;
const GROUNDING_SETTLE_MS = 3300;
const WORLD_SETTLE_MS = 3200;

export const FIRST_OPEN_WORLD_CAMERA_TRANSITION_MS = 2800;

function ReturnMark() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M19 5v7.5a3 3 0 0 1-3 3H6m4-4-4 4 4 4" />
    </svg>
  );
}

function splitExpression(expression: string, identity: string) {
  const index = expression.indexOf(identity);
  if (index < 0) return { lead: '', identity, tail: '' };
  return {
    lead: expression.slice(0, index),
    identity,
    tail: expression.slice(index + identity.length),
  };
}

export default function FirstOpenExperience({
  stage,
  submittedExpression,
  groundedIdentity,
  expressionReferent = null,
  placeAnchorRef,
  map,
  worldProjection,
  onSubmit,
  onGroundingSettled,
  onWorldSettled,
}: FirstOpenExperienceProps) {
  const [value, setValue] = useState('');
  const [entryFrame, setEntryFrame] = useState<EntryFrame>('idle');
  const [transmissionSettled, setTransmissionSettled] = useState(true);
  const transmissionTimerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (transmissionTimerRef.current !== null) {
        window.clearTimeout(transmissionTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (stage !== 'entry' || !value.trim() || entryFrame !== 'typing') return;
    const timer = window.setTimeout(() => setEntryFrame('ready'), READY_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [entryFrame, stage, value]);

  const visualFrame: VisualFrame = stage === 'world'
    ? 'world'
    : stage === 'grounding' && transmissionSettled
      ? 'grounding'
      : stage === 'submitting' || stage === 'grounding'
        ? 'transmitting'
        : entryFrame;

  useEffect(() => {
    if (visualFrame !== 'grounding') return;
    const timer = window.setTimeout(onGroundingSettled, GROUNDING_SETTLE_MS);
    return () => window.clearTimeout(timer);
  }, [onGroundingSettled, visualFrame]);

  useEffect(() => {
    if (visualFrame !== 'world') return;
    const timer = window.setTimeout(onWorldSettled, WORLD_SETTLE_MS);
    return () => window.clearTimeout(timer);
  }, [onWorldSettled, visualFrame]);

  const expression = submittedExpression ?? value;
  const groundedExpression = useMemo(
    () => (groundedIdentity ?? expressionReferent)
      ? splitExpression(expression, groundedIdentity ?? expressionReferent ?? '')
      : null,
    [expression, expressionReferent, groundedIdentity],
  );

  const handleChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
    const nextValue = event.target.value;
    setValue(nextValue);
    setEntryFrame(nextValue.trim() ? 'typing' : 'focus');
  };

  const submit = () => {
    const nextExpression = value.trim();
    if (!nextExpression || stage !== 'entry') return;

    if (transmissionTimerRef.current !== null) {
      window.clearTimeout(transmissionTimerRef.current);
    }
    setEntryFrame('ready');
    setTransmissionSettled(false);
    transmissionTimerRef.current = window.setTimeout(() => {
      setTransmissionSettled(true);
      transmissionTimerRef.current = null;
    }, TRANSMISSION_MS);
    onSubmit(nextExpression);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== 'Enter' || event.shiftKey) return;
    event.preventDefault();
    submit();
  };

  return (
    <section
      className={styles.firstOpen}
      data-frame={visualFrame}
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
            {groundedExpression && (
              visualFrame === 'transmitting'
              || visualFrame === 'grounding'
              || visualFrame === 'world'
            ) ? (
              <div className={styles.expressionGrounded} aria-live="polite">
                <span className={styles.exprContext}>{groundedExpression.lead}</span>
                <span ref={placeAnchorRef} className={styles.exprPlace}>
                  <span className={styles.placeLabel}>{groundedExpression.identity}</span>
                </span>
                <span className={styles.exprContext}>{groundedExpression.tail}</span>
              </div>
            ) : (
              <textarea
                rows={1}
                value={stage === 'entry' ? value : expression}
                readOnly={stage !== 'entry'}
                onChange={handleChange}
                onFocus={() => {
                  if (stage === 'entry' && !value.trim()) setEntryFrame('focus');
                }}
                onBlur={() => {
                  if (stage !== 'entry') return;
                  setEntryFrame(value.trim() ? 'ready' : 'idle');
                }}
                onKeyDown={handleKeyDown}
                placeholder="告诉 LiveOS……"
                aria-label="告诉 LiveOS 一件关于生活的事"
              />
            )}
            <span className={styles.lineLeft} aria-hidden="true" />
            <span className={styles.lineRight} aria-hidden="true" />
            <span className={styles.lineResponse} aria-hidden="true" />
            <span className={styles.commitMark} aria-hidden="true">
              <ReturnMark />
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}
