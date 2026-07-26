'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';

import { streamMessage } from '@/services/chat';

import ConversationComposer from './components/ConversationComposer';
import ConversationLayout from './components/ConversationLayout';
import MessageBubble from './components/MessageBubble';
import ThinkingIndicator from './components/ThinkingIndicator';

type MessageRole = 'user' | 'assistant';

interface ConversationMessage {
  id: string;
  role: MessageRole;
  content: string;
}

const STREAM_ERROR_MESSAGE =
  '抱歉,LiveOS 暂时无法完成回复，请稍后重试。';

export default function ConversationFeature() {
  const searchParams = useSearchParams();

  const conversationId =
    searchParams.get('conversation_id') ?? '';

  const initialMessage = searchParams.get('message') ?? '';

  const [messages, setMessages] = useState<ConversationMessage[]>(
    [],
  );
  const [isThinking, setIsThinking] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);

  const initialMessageSentRef = useRef(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const sendConversationMessage = useCallback(
    async (content: string) => {
      const message = content.trim();

      if (!conversationId || !message || isStreaming) {
        return;
      }

      const userMessage: ConversationMessage = {
        id: crypto.randomUUID(),
        role: 'user',
        content: message,
      };

      const assistantMessageId = crypto.randomUUID();

      setMessages((currentMessages) => [
        ...currentMessages,
        userMessage,
      ]);

      setIsThinking(true);
      setIsStreaming(true);

      try {
        await streamMessage({
          conversationId,
          message,
          onChunk: (chunk) => {
            setIsThinking(false);

            setMessages((currentMessages) => {
              const assistantMessageExists =
                currentMessages.some(
                  (item) => item.id === assistantMessageId,
                );

              if (!assistantMessageExists) {
                return [
                  ...currentMessages,
                  {
                    id: assistantMessageId,
                    role: 'assistant',
                    content: chunk,
                  },
                ];
              }

              return currentMessages.map((item) =>
                item.id === assistantMessageId
                  ? {
                    ...item,
                    content: item.content + chunk,
                  }
                  : item,
              );
            });
          },
        });
      } catch (error: unknown) {
        console.error('Failed to stream message:', error);

        setMessages((currentMessages) => [
          ...currentMessages,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: STREAM_ERROR_MESSAGE,
          },
        ]);
      } finally {
        setIsThinking(false);
        setIsStreaming(false);
      }
    },
    [conversationId, isStreaming],
  );

  useEffect(() => {
    if (
      !initialMessage ||
      !conversationId ||
      initialMessageSentRef.current
    ) {
      return;
    }

    initialMessageSentRef.current = true;
    void sendConversationMessage(initialMessage);
  }, [
    conversationId,
    initialMessage,
    sendConversationMessage,
  ]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: 'auto',
      block: 'end',
    });
  }, [messages, isThinking]);

  return (
    <ConversationLayout>
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="min-h-0 flex-1 overflow-y-auto pr-2">
          {messages.map((message) => (
            <MessageBubble
              key={message.id}
              role={message.role}
              content={message.content}
            />
          ))}

          {isThinking && <ThinkingIndicator />}

          <div ref={bottomRef} />
        </div>

        <ConversationComposer
          disabled={isStreaming}
          onSubmit={(message) => {
            void sendConversationMessage(message);
          }}
        />
      </div>
    </ConversationLayout>
  );
}