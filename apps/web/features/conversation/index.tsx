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
import {
  getDecision,
  type DecisionResult,
} from '@/services/decision';
import { createClientId } from '@/lib/createClientId';

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
  const [isListening, setIsListening] = useState(false);
  const [hasRuntimeError, setHasRuntimeError] = useState(false);

  const [profile, setProfile] = useState<LivingProfile | null>(null);
  const [isProfileLoading, setIsProfileLoading] = useState(false);
  const [decision, setDecision] = useState<DecisionResult | null>(null);

  const initialMessageSentRef = useRef(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const profileHref = conversationId
    ? `/workspace/profile?conversation_id=${encodeURIComponent(conversationId)}`
    : '/workspace/profile';

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

  const loadDecision = useCallback(async () => {
    if (!conversationId) {
      return;
    }

    try {
      setDecision(await getDecision(conversationId));
    } catch (error: unknown) {
      // Decision availability must not block the existing conversation flow.
      console.error('Failed to load current decision:', error);
      setDecision(null);
    }
  }, [conversationId]);

  useEffect(() => {
    // These loaders synchronize the existing profile/decision APIs on entry.
    if (!initialMessage) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      void loadProfile();
      void loadDecision();
    }
  }, [initialMessage, loadDecision, loadProfile]);

  const sendConversationMessage = useCallback(
    async (content: string) => {
      const message = content.trim();

      if (!conversationId || !message || isStreaming) {
        return;
      }

      const userMessage: ConversationMessage = {
        id: createClientId(),
        role: 'user',
        content: message,
      };

      const assistantMessageId = createClientId();

      setMessages((currentMessages) => [
        ...currentMessages,
        userMessage,
      ]);

      setHasRuntimeError(false);
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
              void loadDecision();
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

        await loadDecision();
      } catch (error: unknown) {
        console.error('Failed to stream message:', error);

        setMessages((currentMessages) => [
          ...currentMessages,
          {
            id: createClientId(),
            role: 'assistant',
            content: STREAM_ERROR_MESSAGE,
          },
        ]);
        setHasRuntimeError(true);
      } finally {
        setIsThinking(false);
        setIsStreaming(false);
      }

    },
    [conversationId, isStreaming, loadDecision, loadProfile],
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

  const isInitialTurnStarting = Boolean(initialMessage)
    && messages.length === 1;

  return (
    <ConversationLayout
      conversationId={conversationId}
      coreState={
        hasRuntimeError
          ? 'error'
          : isProfileLoading
            ? 'understanding'
            : isInitialTurnStarting || isThinking || isStreaming
              ? 'thinking'
              : isListening || messages.length > 0
                ? 'listening'
                : 'idle'
      }
    >
      <div className="grid h-full min-h-0 xl:grid-cols-[minmax(0,1fr)_340px]">
        <section className="flex min-h-0 flex-col">
          <div className="min-h-0 flex-1 overflow-y-auto px-5 py-7 sm:px-8 lg:px-12">
            <div className="mx-auto w-full max-w-5xl">
              <CurrentProblem profile={profile} />
              <LivingState profile={profile} decision={decision} />

              <p className="mb-4 mt-10 font-mono text-[10px] tracking-[0.16em] text-slate-600">
                RECENT CONVERSATION
              </p>
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
            onListeningChange={setIsListening}
          />
        </section>

        <div className="hidden min-h-0 xl:block">
          <ProfileWorkspace
            profile={profile}
            isLoading={isProfileLoading}
          />
        </div>
      </div>
    </ConversationLayout>
  );
}

function CurrentProblem({ profile }: { profile: LivingProfile | null }) {
  const location = profile?.preferred_city || profile?.work_location;
  const title = location ? `${location}租房` : '当前居住问题';

  return (
    <section aria-labelledby="current-problem" className="border-b border-white/[0.06] pb-7">
      <p id="current-problem" className="font-mono text-[10px] tracking-[0.16em] text-blue-400">
        CURRENT PROBLEM
      </p>
      <h1 className="mt-3 text-2xl font-medium tracking-tight text-slate-100 sm:text-3xl">
        {title}
      </h1>
      <p className="mt-2 max-w-xl text-sm leading-6 text-slate-500">
        找到预算、独居和通勤之间更合理的方案。
      </p>
    </section>
  );
}

function LivingState({
  profile,
  decision,
}: {
  profile: LivingProfile | null;
  decision: DecisionResult | null;
}) {
  const isDecision = decision?.status === 'ready' && Boolean(decision.summary);
  const summaryParts = decision?.summary?.split(' 下一步：', 2) ?? [];
  const reason = decision?.reasons[0];
  const tradeOff = decision?.trade_offs[0];

  return (
    <section aria-labelledby="living-state" className="pt-8">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p id="living-state" className="font-mono text-[10px] tracking-[0.16em] text-blue-400">
            {isDecision ? 'CURRENT DECISION' : 'CURRENT UNDERSTANDING'}
          </p>
          <h2 className="mt-2 text-xl font-medium tracking-tight text-slate-100">
            {isDecision ? '当前判断' : 'LiveOS 正在理解你的居住需求'}
          </h2>
        </div>
        <span className="text-xs text-slate-600">{isDecision ? 'Decision' : 'Understanding'}</span>
      </div>

      {isDecision ? (
        <div className="mt-5 space-y-5">
          <p className="max-w-3xl text-base leading-7 text-slate-300">{summaryParts[0]}</p>
          {reason && <StateItem label="主要依据" value={reason.description} />}
          {tradeOff && <StateItem label="主要取舍" value={tradeOff.description} />}
          {summaryParts[1] && <StateItem label="NEXT" value={summaryParts[1]} />}
        </div>
      ) : (
        <div className="mt-5 max-w-3xl space-y-3 text-sm leading-6 text-slate-400">
          <p>{getUnderstandingCopy(profile)}</p>
          <p className="text-slate-600">LiveOS 会继续基于这些信息推进判断。</p>
        </div>
      )}
    </section>
  );
}

function StateItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-l border-blue-500/30 pl-4">
      <p className="font-mono text-[10px] tracking-[0.12em] text-slate-600">{label}</p>
      <p className="mt-1 text-sm leading-6 text-slate-400">{value}</p>
    </div>
  );
}

function getUnderstandingCopy(profile: LivingProfile | null) {
  const location = profile?.work_location || profile?.preferred_city;
  const details = [
    location ? `你正在寻找${location}附近的居住方案。` : null,
    typeof profile?.budget === 'number' ? `预算约 ¥${profile.budget.toLocaleString('zh-CN')}` : null,
    profile?.family_size === 1 ? '倾向独立居住' : null,
    typeof profile?.commute_minutes === 'number' ? `通勤希望 ≤${profile.commute_minutes} 分钟` : null,
  ].filter(Boolean);

  return details.length > 0
    ? details.join('，')
    : 'LiveOS 正在根据当前对话理解你的需求。';
}
