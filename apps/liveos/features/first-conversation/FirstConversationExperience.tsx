'use client';

import { useEffect, useRef } from 'react';
import Wordmark from '../../components/brand/Wordmark';
import { useConversationSession } from '../../runtime/useConversationSession';
import ExpressionComposer from './ExpressionComposer';
import styles from './first-conversation.module.css';

export default function FirstConversationExperience({ initialConversationId }: { initialConversationId: string }) {
  const { messages, isResponding, isRestoring, error, submit } = useConversationSession(initialConversationId);
  const started = messages.length > 0 || isRestoring;
  const transcriptEnd = useRef<HTMLDivElement>(null);

  useEffect(() => {
    transcriptEnd.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages]);

  return (
    <main className={styles.surface} data-started={started}>
      <header className={styles.brand}><Wordmark /></header>
      {!started && (
        <section className={styles.welcome}>
          <p className={styles.eyebrow}>A SPACE TO THINK THINGS THROUGH</p>
          <h1>你的生活，<br />可以从一句话开始。</h1>
          <p className={styles.invitation}>最近有什么事，正在你心里？</p>
        </section>
      )}
      {started && (
        <section className={styles.conversation} aria-label="对话" aria-live="polite">
          {messages.map((message) => (
            <article className={styles.turn} key={message.id} data-role={message.role}>
              <span className={styles.speaker}>{message.role === 'user' ? '你' : 'LIVEOS'}</span>
              <p>{message.content || (isResponding && message.role === 'assistant' ? '…' : '')}</p>
            </article>
          ))}
          {isRestoring && <p className={styles.status}>正在恢复对话…</p>}
          {error && <p className={styles.error} role="status">{error}</p>}
          <div ref={transcriptEnd} />
        </section>
      )}
      <ExpressionComposer onSubmit={submit} disabled={isResponding || isRestoring} />
    </main>
  );
}
