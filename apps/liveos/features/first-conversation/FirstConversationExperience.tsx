'use client';

import Image from 'next/image';
import firstOpenBackground from '../../../../docs/03_Design/UI_Library/ Screens/01_First_Open/assets/first-open-mountain-background.png';
import Wordmark from '../../components/brand/Wordmark';
import { useConversationSession } from '../../runtime/useConversationSession';
import ConversationTranscript from './ConversationTranscript';
import ExpressionComposer from './ExpressionComposer';
import styles from './first-conversation.module.css';

export default function FirstConversationExperience({ initialConversationId }: { initialConversationId: string }) {
  const { conversationId, messages, isResponding, isRestoring, error, submit } = useConversationSession(initialConversationId);
  const started = messages.length > 0 || isRestoring;

  return (
    <main className={`${styles.surface} ${started ? styles.conversationSurface : ''}`}>
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
      <footer className={styles.entry}>
        <p className={styles.status} role="status">
          {error ?? (isRestoring ? '正在恢复对话…' : '')}
        </p>
        <ExpressionComposer onSubmit={submit} disabled={isResponding || isRestoring} conversation={started} />
      </footer>
    </main>
  );
}
