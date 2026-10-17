'use client';

import { useEffect, useRef } from 'react';
import type { ConversationMessage } from '@/lib/runtimePresentationContract';
import styles from './UnifiedSurface.module.css';

interface ConversationProps {
  messages: readonly ConversationMessage[];
  isResponding: boolean;
}

export default function Conversation({ messages, isResponding }: ConversationProps) {
  const viewport = useRef<HTMLDivElement>(null);
  const following = useRef(true);
  useEffect(() => {
    const element = viewport.current;
    if (element && following.current) element.scrollTop = element.scrollHeight;
  }, [messages]);
  return (
    <div
      ref={viewport}
      className={styles.conversation}
      role="log"
      aria-label="与 LiveOS 的对话"
      aria-live="polite"
      aria-relevant="additions text"
      onScroll={() => {
        const element = viewport.current;
        if (element) following.current = element.scrollHeight - element.scrollTop - element.clientHeight < 80;
      }}
    >
      {messages.map((message, index) => {
        const pending = isResponding && index === messages.length - 1 && !message.content;
        if (!message.content && !pending) return null;
        return (
          <article key={message.id} className={styles.message} data-role={message.role} aria-busy={pending}>
            <span className={styles.speaker}>{message.role === 'user' ? '你' : 'LiveOS'}</span>
            <p>{message.content || '正在回应…'}</p>
          </article>
        );
      })}
    </div>
  );
}
