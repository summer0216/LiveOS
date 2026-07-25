'use client';

import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';

import { streamMessage } from '@/services/chat';

import ConversationLayout from './components/ConversationLayout';
import MessageBubble from './components/MessageBubble';
import ThinkingIndicator from './components/ThinkingIndicator';

export default function ConversationFeature() {
  const searchParams = useSearchParams();

  const conversationId =
    searchParams.get('conversation_id') ?? '';

  const userMessage = searchParams.get('message') ?? '';

  const [reply, setReply] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const hasSentRef = useRef(false);
  const bottomRef = useRef<HTMLDivElement>(null);


  useEffect(() => {
    if (!conversationId || !userMessage || hasSentRef.current) {
      return;
    }

    hasSentRef.current = true;

    setReply('');
    setErrorMessage('');
    setIsThinking(true);

    streamMessage({
      conversationId,
      message: userMessage,
      onChunk: (chunk) => {
        setIsThinking(false);
        setReply((currentReply) => currentReply + chunk);
      },
    })
      .catch((error: unknown) => {
        console.error('Failed to stream message:', error);

        setErrorMessage(
          '抱歉，LiveOS 暂时无法完成回复，请稍后重试。',
        );
      })
      .finally(() => {
        setIsThinking(false);
      });
  }, [conversationId, userMessage]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: reply ? "smooth" : "auto",
    });
  }, [reply, isThinking]);

  return (
    <ConversationLayout>
      {userMessage && (
        <MessageBubble role="user" content={userMessage} />
      )}

      {isThinking && <ThinkingIndicator />}

      {reply && (
        <MessageBubble role="assistant" content={reply} />
      )}

      {errorMessage && (
        <MessageBubble role="assistant" content={errorMessage} />
      )}
      <div ref={bottomRef} />
    </ConversationLayout>

  );
}