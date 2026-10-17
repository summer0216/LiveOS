'use client';

import { useEffect, type ReactNode } from 'react';
import {
  WORLD_SETTLE_MS,
  type WorldRevealPresentation,
  type GeographicProjection,
} from '@/lib/runtimePresentationContract';
import RealityAnchorProjection from '@/features/possible-life-world/RealityAnchorProjection';
import { deriveSurfacePresentation, type SurfacePresentationFacts } from './presentationPolicy';
import Conversation from './Conversation';
import ExpressionEntry from './ExpressionEntry';
import styles from './UnifiedSurface.module.css';

interface UnifiedSurfaceProps extends WorldRevealPresentation<HTMLSpanElement>, SurfacePresentationFacts {
  conversationError: string | null;
  map?: ReactNode;
  mapProjection: GeographicProjection | null;
  mapZoom: number | null;
  onSubmit: (expression: string) => Promise<void>;
}

export default function UnifiedSurface({
  messages, isResponding, isRestoringConversation, isSubmittingExpression,
  groundedReality, requiresCameraAnchor, revealStarted, revealComplete, geographicGroundReady, cameraReady, consequenceFocus,
  conversationError, placeAnchorRef, map, mapProjection, mapZoom, onSubmit, onWorldSettled,
}: UnifiedSurfaceProps) {
  const policy = deriveSurfacePresentation({
    messages, isResponding, isRestoringConversation, isSubmittingExpression,
    groundedReality, requiresCameraAnchor, revealStarted, revealComplete, geographicGroundReady, cameraReady, consequenceFocus,
  });
  const subjectIdentity = groundedReality?.identity;
  useEffect(() => {
    if (!policy.reportRevealCompletion) return;
    const timer = window.setTimeout(onWorldSettled, WORLD_SETTLE_MS);
    return () => window.clearTimeout(timer);
  }, [policy.reportRevealCompletion, onWorldSettled]);

  return (
    <section className={styles.surface} data-started={policy.started} data-world-visible={policy.worldVisible}
      data-visual-emphasis={policy.visualEmphasis}
      data-consequence-property={consequenceFocus?.focusPropertyId}
      data-consequence-subject={consequenceFocus?.focusSubject?.identity}
      data-consequence-possible-life={consequenceFocus?.focusPossibleLife?.possible_life.id}
      aria-label="LiveOS">
      {map && <div className={styles.world}>{map}
        <RealityAnchorProjection
          identity={groundedReality?.identity ?? null}
          location={groundedReality?.center ?? null}
          projection={mapProjection}
          zoom={mapZoom}
          visible={policy.anchorVisible}
        />
      </div>}
      <header className={styles.header}>LiveOS</header>
      <div className={styles.welcome} aria-hidden={policy.started}>
        <h1>你的生活，从哪里开始？</h1>
        <p>一件事，一个想法，都可以。</p>
      </div>
      {policy.anchorMounted && (
        <span ref={placeAnchorRef} className={styles.cameraAnchor} aria-hidden="true">{subjectIdentity}</span>
      )}
      {policy.started && <Conversation messages={messages} isResponding={isResponding} />}
      <div className={styles.entry}>
        {(conversationError || isRestoringConversation) && (
          <p className={styles.notice} role="status">{conversationError ?? '正在恢复对话…'}</p>
        )}
        <ExpressionEntry
          disabled={policy.entryDisabled}
          onSubmit={onSubmit}
        />
      </div>
    </section>
  );
}
