'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';

import { streamMessage } from '@/services/chat';

import ConversationComposer from './components/ConversationComposer';
import ConversationLayout from './components/ConversationLayout';
import MessageBubble from './components/MessageBubble';
import ThinkingIndicator from './components/ThinkingIndicator';
import ProfileWorkspace from './components/ProfileWorkspace';

import {
  getLivingProfile,
  type LivingProfile,
} from '@/services/profile';

type MessageRole = 'user' | 'assistant';

interface ConversationMessage {
  id: string;
  role: MessageRole;
  content: string;
}

const STREAM_ERROR_MESSAGE =
  '抱歉，LiveOS 暂时无法完成回复，请稍后重试。';

const WELCOME_MESSAGE: ConversationMessage = {
  id: 'liveos-welcome',
  role: 'assistant',
  content:
    '你好，我是你的 LiveOS 决策助手。告诉我你理想的居住情况——现在对你来说什么最重要？',
};

export default function ConversationFeature() {
  const searchParams = useSearchParams();

  const conversationId =
    searchParams.get('conversation_id') ?? '';

  const initialMessage = searchParams.get('message') ?? '';

  const [messages, setMessages] = useState<ConversationMessage[]>(
    [WELCOME_MESSAGE],
  );
  const [isThinking, setIsThinking] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);

  const [profile, setProfile] = useState<LivingProfile | null>(null);
  const [isProfileLoading, setIsProfileLoading] = useState(false);

  const initialMessageSentRef = useRef(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const profileHref = conversationId
    ? `/profile?conversation_id=${encodeURIComponent(conversationId)}`
    : '/profile';

  const loadProfile = useCallback(async () => {
    if (!conversationId) {
      return;
    }
    setIsProfileLoading(true);
    try {
      const livingProfile =
        await getLivingProfile(conversationId);

      setProfile(livingProfile);
    } catch (error: unknown) {
      console.error(
        'Failed to load living profile:',
        error,
      );
    } finally {
      setIsProfileLoading(false);
    }
  }, [conversationId]);

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
        let hasRefreshedProfile = false;

        await streamMessage({
          conversationId,
          message,
          onChunk: (chunk) => {
            setIsThinking(false);

            /*
             * 后端在开始 Streaming 前已经完成 Profile 更新。
             * 因此首个 Chunk 到达时即可刷新 Workspace。
             */
            if (!hasRefreshedProfile) {
              hasRefreshedProfile = true;
              void loadProfile();
            }

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

        /*
         * 若模型没有返回任何 Chunk，也做一次兜底刷新。
         */
        if (!hasRefreshedProfile) {
          await loadProfile();
        }
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
    [conversationId, isStreaming, loadProfile],
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
    <ConversationLayout
      profileHref={profileHref}
      profileReady={Boolean(profile)}
    >
      <div className="grid h-full min-h-0 xl:grid-cols-[minmax(0,1fr)_340px]">
        <section className="flex min-h-0 flex-col">
          <div className="min-h-0 flex-1 overflow-y-auto px-5 py-7 sm:px-8 lg:px-12">
            <div className="mx-auto w-full max-w-5xl">
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
          </div>

          <ConversationComposer
            disabled={isStreaming}
            profileHref={profileHref}
            profileReady={Boolean(profile)}
            onSubmit={(message) => {
              void sendConversationMessage(message);
            }}
          />
        </section>

        <div className="hidden min-h-0 xl:block">
          <ProfileWorkspace
            profile={profile}
            isLoading={isProfileLoading}
            profileHref={profileHref}
          />
        </div>
      </div>
    </ConversationLayout>
  );
}
