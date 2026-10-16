'use client';

import { useEffect, useRef } from 'react';
import type { PresentedMessage } from '../../contracts/conversation';
import MarkdownResponse from './MarkdownResponse';
import ConversationIdentity from './ConversationIdentity';
import styles from './first-conversation.module.css';

export default function ConversationTranscript({ messages, isResponding }: {
  messages: readonly PresentedMessage[];
  isResponding: boolean;
}) {
  const viewport = useRef<HTMLDivElement>(null);
  const following = useRef(true);
  useEffect(() => {
    if (following.current && viewport.current) {
      viewport.current.scrollTop = viewport.current.scrollHeight;
    }
  }, [messages]);

  return (
    <div className={styles.transcript} ref={viewport} onScroll={() => {
      const element = viewport.current;
      if (element) following.current = element.scrollHeight - element.scrollTop - element.clientHeight < 80;
    }}>
      <section className={styles.conversation} role="log" aria-label="对话" aria-busy={isResponding}>
        {messages.map((message) => (
          <article className={message.role === 'user' ? styles.user : styles.assistant} key={message.id}>
            <ConversationIdentity role={message.role} />
            <div className={styles.messageContent}>
              {message.role === 'user'
                ? <p className={styles.expression}>{message.content}</p>
                : <MarkdownResponse content={message.content} />}
            </div>
          </article>
        ))}
      </section>
    </div>
  );
}
