'use client';

import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';

import { sendMessage } from '@/services/chat';

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

  useEffect(() => {
    if (!conversationId || !userMessage || hasSentRef.current) {
      return;
    }

    hasSentRef.current = true;
    setIsThinking(true);
    setErrorMessage('');

    sendMessage(conversationId, userMessage)
      .then((response) => {
        setReply(response.reply);
      })
      .catch((error: unknown) => {
        console.error('Failed to send message:', error);

        setErrorMessage(
          '抱歉，LiveOS 暂时无法完成回复，请稍后重试。',
        );
      })
      .finally(() => {
        setIsThinking(false);
      });
  }, [conversationId, userMessage]);

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
        <MessageBubble
          role="assistant"
          content={errorMessage}
        />
      )}
    </ConversationLayout>
  );
}