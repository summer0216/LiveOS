'use client';

import Wordmark from '../../components/brand/Wordmark';
import { useConversationSession } from '../../runtime/useConversationSession';
import ConversationTranscript from './ConversationTranscript';
import ExpressionComposer from './ExpressionComposer';
import styles from './first-conversation.module.css';

export default function FirstConversationExperience({ initialConversationId }: { initialConversationId: string }) {
  const { messages, isResponding, isRestoring, error, submit } = useConversationSession(initialConversationId);
  const started = messages.length > 0 || isRestoring;

  return (
    <main className={styles.surface}>
      <header className={styles.brand}><Wordmark /></header>
      {started ? (
        <ConversationTranscript messages={messages} isResponding={isResponding} />
      ) : (
        <section className={styles.welcome}>
          <h1>你的生活，可以从一句话开始。</h1>
          <p>最近有什么事，正在你心里？</p>
        </section>
      )}
      <footer className={styles.entry}>
        <p className={styles.status} role="status">
          {error ?? (isRestoring ? '正在恢复对话…' : isResponding ? 'LiveOS 正在回应，你可以继续写下想法。' : '')}
        </p>
        <ExpressionComposer onSubmit={submit} disabled={isResponding || isRestoring} />
      </footer>
    </main>
  );
}
