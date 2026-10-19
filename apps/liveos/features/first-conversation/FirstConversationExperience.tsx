'use client';

import Image from 'next/image';
import Wordmark from '../../components/brand/Wordmark';
import { useState } from 'react';
import firstOpenBackground from '../../../../docs/03_Design/UI_Library/ Screens/01_First_Open/assets/first-open-mountain-background.png';
import { useConversationSession } from '../../runtime/useConversationSession';
import { useGroundedPlace } from '../living-world/useGroundedPlace';
import WorldFocusSurface from '../living-world/WorldFocusSurface';
import ConversationTranscript from './ConversationTranscript';
import ExpressionComposer from './ExpressionComposer';
import styles from './first-conversation.module.css';

export default function FirstConversationExperience({ initialConversationId }: { initialConversationId: string }) {
  const { conversationId, messages, isResponding, isRestoring, error, submit } = useConversationSession(initialConversationId);
  const [realityRefresh, setRealityRefresh] = useState(0);
  const [expandedConversationId, setExpandedConversationId] = useState<string | null>(null);
  const { place, isRestoring: isRestoringPlace, error: realityError } = useGroundedPlace(conversationId, realityRefresh);
  const isResuming = Boolean(initialConversationId) && (isRestoring || isRestoringPlace);
  const refreshReality = () => setRealityRefresh((current) => current + 1);
  const submitAndRefreshReality = async (expression: string) => {
    if (place) setExpandedConversationId(conversationId);
    await submit(expression, refreshReality);
    refreshReality();
  };
  const started = messages.length > 0 || isRestoring;
  const entry = (
    <footer className={styles.entry}>
      <p className={styles.status} role="status">
        {error ?? realityError ?? (isRestoring ? '正在恢复对话…' : '')}
      </p>
      <ExpressionComposer onSubmit={submitAndRefreshReality} disabled={isResponding || isRestoring} conversation={started && !place} />
    </footer>
  );

  if (isResuming) {
    return <main className={styles.surface} aria-busy="true"><p className={styles.status} role="status">正在恢复…</p></main>;
  }

  return (
    <main className={`${styles.surface} ${started && !place ? styles.conversationSurface : ''}`}>
      {place ? (
        <WorldFocusSurface
          place={place}
          conversation={<ConversationTranscript messages={messages} isResponding={isResponding} conversationId={conversationId} />}
          entry={entry}
          animateAppearance={realityRefresh > 0}
          isResponding={isResponding}
          conversationExpanded={expandedConversationId === conversationId}
          onConversationExpandedChange={(expanded) => setExpandedConversationId(expanded ? conversationId : null)}
        />
      ) : (
        <>
          <Image className={styles.firstOpenBackground} src={firstOpenBackground} alt="" fill priority sizes="100vw" />
          <header className={styles.brand}><Wordmark /></header>
          {started ? (
            <ConversationTranscript messages={messages} isResponding={isResponding} conversationId={conversationId} />
          ) : (
            <section className={styles.welcome}>
              <h1>你的生活，可以从一句话开始。</h1>
              <p>最近有什么事，正在你心里？</p>
            </section>
          )}
          {entry}
        </>
      )}
    </main>
  );
}
