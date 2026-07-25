'use client';

import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';

import { sendMessage } from '@/services/chat';

import ConversationLayout from './components/ConversationLayout';
import MessageBubble from './components/MessageBubble';

export default function ConversationFeature() {
  const searchParams = useSearchParams();

  const conversationId =
    searchParams.get('conversation_id') ?? '';

  const userMessage = searchParams.get('message') ?? '';

  const [reply, setReply] = useState('');
  const hasSentRef = useRef(false);

  useEffect(() => {
    if (!conversationId || !userMessage || hasSentRef.current) {
      return;
    }

    hasSentRef.current = true;

    sendMessage(conversationId, userMessage)
      .then((response) => {
        setReply(response.reply);
      })
      .catch((error: unknown) => {
        console.error('Failed to send message:', error);
        setReply('抱歉，AI 服务暂时不可用，请稍后重试。');
      });
  }, [conversationId, userMessage]);

  return (
    <ConversationLayout>
      {userMessage && (
        <MessageBubble role="user" content={userMessage} />
      )}

      {reply && (
        <MessageBubble role="assistant" content={reply} />
      )}
    </ConversationLayout>
  );
}