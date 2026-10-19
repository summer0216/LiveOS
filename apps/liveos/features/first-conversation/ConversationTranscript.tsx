'use client';

import { useEffect, useRef } from 'react';
import type { PresentedMessage } from '../../contracts/conversation';
import MarkdownResponse from './MarkdownResponse';
import ConversationIdentity from './ConversationIdentity';
import MessageFeedback from './MessageFeedback';
import MessageCopy from './MessageCopy';
import styles from './first-conversation.module.css';

const messageTimeFormat = new Intl.DateTimeFormat('en-GB', {
  hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
});

function messageTime(createdAt?: string) {
  if (!createdAt) return null;
  const date = new Date(createdAt);
  return Number.isNaN(date.getTime()) ? null : messageTimeFormat.format(date);
}

export default function ConversationTranscript({ messages, isResponding, conversationId }: {
  messages: readonly PresentedMessage[];
  isResponding: boolean;
  conversationId?: string;
}) {
  const viewport = useRef<HTMLDivElement>(null);
  const following = useRef(true);
  const latestAssistant = messages.findLast((message) => message.role === 'assistant');
  useEffect(() => {
    if (following.current && viewport.current) {
      viewport.current.scrollTop = viewport.current.scrollHeight;
    }
  }, [messages]);
  useEffect(() => {
    const element = viewport.current;
    if (!element?.firstElementChild) return;
    const observer = new ResizeObserver(() => {
      if (following.current) element.scrollTop = element.scrollHeight;
    });
    observer.observe(element.firstElementChild);
    return () => observer.disconnect();
  }, []);

  return (
    <div className={styles.transcript} ref={viewport} onScroll={() => {
      const element = viewport.current;
      if (element) following.current = element.scrollHeight - element.scrollTop - element.clientHeight < 80;
    }}>
      <section className={styles.conversation} role="log" aria-label="对话" aria-busy={isResponding}>
        {messages.map((message) => {
          const isThinking = isResponding && message.role === 'assistant' && message.id === latestAssistant?.id && !message.content.trim();
          const time = message.role === 'assistant'
            ? messageTime(message.created_at)
            : null;
          return (
            <article
              className={
                message.role === 'user'
                  ? styles.user
                  : `${styles.assistant} ${isThinking ? styles.thinkingMessage : ''}`
              }
              key={message.id}
            >
              <ConversationIdentity role={message.role} />

              <div className={styles.messageBody}>
                <div className={styles.messageContent}>
                  {message.role === 'user' ? (
                    <p className={styles.expression}>{message.content}</p>
                  ) : (
                    <>
                      {isThinking ? (
                        <span
                          className={styles.thinking}
                          role="status"
                          aria-label="LiveOS 正在思考"
                        >
                          <span aria-hidden="true" />
                          <span aria-hidden="true" />
                          <span aria-hidden="true" />
                        </span>
                      ) : (
                        <MarkdownResponse content={message.content} />
                      )}
                    </>
                  )}
                </div>

                {(time ||
                  (conversationId &&
                    message.role === 'assistant' &&
                    message.created_at &&
                    message.content.trim())) && (
                    <div className={styles.messageActions}>
                      {conversationId &&
                        message.role === 'assistant' &&
                        message.created_at &&
                        message.content.trim() && (
                          <>
                            <MessageCopy content={message.content} />
                            <MessageFeedback
                              key={message.feedback ?? 'none'}
                              conversationId={conversationId}
                              messageId={message.id}
                              feedback={message.feedback ?? null}
                            />
                          </>
                        )}

                      {time && (
                        <time
                          className={styles.messageTime}
                          dateTime={message.created_at}
                        >
                          {time}
                        </time>
                      )}
                    </div>
                  )}
              </div>
            </article>

          );
        })}
      </section>
    </div>
  );
}
