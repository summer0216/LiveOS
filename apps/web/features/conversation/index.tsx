'use client';

import {
  type RefObject,
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';
import { useSearchParams } from 'next/navigation';

import { streamMessage, type DecisionChange } from '@/services/chat';

import ConversationComposer from './components/ConversationComposer';
import ConversationLayout from './components/ConversationLayout';
import MessageBubble from './components/MessageBubble';
import ThinkingIndicator from './components/ThinkingIndicator';
import ProfileWorkspace from './components/ProfileWorkspace';

import { getLivingProfile, type LivingProfile } from '@/services/profile';
import { getDecision, type DecisionResult } from '@/services/decision';
import { getProperty, type Property } from '@/services/property';
import {
  getLivingDecisionResume,
  type ActionProgressStatus,
  type CurrentActionProgress,
  type LatestVerifiedAction,
  type VerificationOutcomeStatus,
} from '@/services/resume';
import { createClientId } from '@/lib/createClientId';

type MessageRole = 'user' | 'assistant';

interface ConversationMessage {
  id: string;
  role: MessageRole;
  content: string;
}

const PROFILE_VALUE_FIELDS = [
  'work_location',
  'budget',
  'commute_minutes',
  'preferred_city',
  'family_size',
  'has_pet',
] as const;

function hasMeaningfulProfileChange(
  previousProfile: LivingProfile,
  currentProfile: LivingProfile,
): boolean {
  return PROFILE_VALUE_FIELDS.some(
    (field) => previousProfile[field] !== currentProfile[field],
  );
}

function hasActionStateChanged(
  currentAction: CurrentActionProgress | null,
  latestVerifiedAction: LatestVerifiedAction | null,
  nextAction: CurrentActionProgress | null,
  nextLatestVerifiedAction: LatestVerifiedAction | null,
): boolean {
  return (
    JSON.stringify(currentAction) !== JSON.stringify(nextAction) ||
    JSON.stringify(latestVerifiedAction) !==
      JSON.stringify(nextLatestVerifiedAction)
  );
}

const STREAM_ERROR_MESSAGE = '抱歉，LiveOS 暂时无法完成回复，请稍后重试。';

const WELCOME_MESSAGE: ConversationMessage = {
  id: 'liveos-welcome',
  role: 'assistant',
  content:
    '你好，我是你的 LiveOS 决策助手。告诉我你理想的居住情况——现在对你来说什么最重要？',
};

export default function ConversationFeature() {
  const searchParams = useSearchParams();

  const conversationId = searchParams.get('conversation_id') ?? '';

  const initialMessage = searchParams.get('message') ?? '';

  const [messages, setMessages] = useState<ConversationMessage[]>([
    WELCOME_MESSAGE,
  ]);
  const [isThinking, setIsThinking] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [hasRuntimeError, setHasRuntimeError] = useState(false);

  const [profile, setProfile] = useState<LivingProfile | null>(null);
  const [isProfileLoading, setIsProfileLoading] = useState(false);
  const [decision, setDecision] = useState<DecisionResult | null>(null);
  const [candidate, setCandidate] = useState<Property | null>(null);
  const [actionProgress, setActionProgress] =
    useState<CurrentActionProgress | null>(null);
  const [latestVerifiedAction, setLatestVerifiedAction] =
    useState<LatestVerifiedAction | null>(null);
  const [changeExplanation, setChangeExplanation] = useState<string | null>(
    null,
  );
  const [isConversationExpanded, setIsConversationExpanded] = useState(false);

  const initialMessageSentRef = useRef(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const decisionSurfaceRef = useRef<HTMLElement>(null);

  const loadProfile = useCallback(async () => {
    if (!conversationId) {
      return;
    }
    setIsProfileLoading(true);
    try {
      const livingProfile = await getLivingProfile(conversationId);

      setProfile(livingProfile);
      return livingProfile;
    } catch (error: unknown) {
      console.error('Failed to load living profile:', error);
      return undefined;
    } finally {
      setIsProfileLoading(false);
    }
  }, [conversationId]);

  const refreshDecision = useCallback(async () => {
    if (!conversationId) {
      return false;
    }

    try {
      const refreshedDecision = await getDecision(conversationId);
      // Never carry a previous Action Progress label across a Decision transition.
      // The matching current state is restored after the new Decision is settled.
      setActionProgress(null);
      setDecision((currentDecision) => {
        if (refreshedDecision.status === 'ready') {
          return refreshedDecision;
        }

        return currentDecision?.status === 'ready'
          ? currentDecision
          : refreshedDecision;
      });
      return true;
    } catch (error: unknown) {
      // Decision availability must not block the existing conversation flow.
      console.error('Failed to load current decision:', error);
      return false;
    }
  }, [conversationId]);

  const loadResumeState = useCallback(async () => {
    if (!conversationId) {
      return;
    }

    setIsProfileLoading(true);
    try {
      const resumeState = await getLivingDecisionResume(conversationId);
      setProfile(resumeState.profile);
      setDecision(resumeState.decision);
      setActionProgress(resumeState.action_progress);
      setLatestVerifiedAction(resumeState.latest_verified_action);
    } catch (error: unknown) {
      console.error('Failed to resume living decision:', error);
    } finally {
      setIsProfileLoading(false);
    }
  }, [conversationId]);

  const loadActionProgress = useCallback(async () => {
    if (!conversationId) return;
    try {
      const resumeState = await getLivingDecisionResume(conversationId);
      setActionProgress(resumeState.action_progress);
      setLatestVerifiedAction(resumeState.latest_verified_action);
      return resumeState;
    } catch (error: unknown) {
      console.error('Failed to load current Action Progress:', error);
      return undefined;
    }
  }, [conversationId]);

  const loadCandidate = useCallback(async () => {
    if (!conversationId) {
      return;
    }

    try {
      setCandidate(await getProperty(conversationId));
    } catch (error: unknown) {
      console.error('Failed to load candidate property:', error);
    }
  }, [conversationId]);

  useEffect(() => {
    if (!initialMessage) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      void loadResumeState();
    }
  }, [initialMessage, loadResumeState]);

  useEffect(() => {
    if (initialMessage) {
      return;
    }

    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadCandidate();
  }, [initialMessage, loadCandidate]);

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

      setMessages((currentMessages) => [...currentMessages, userMessage]);
      setIsConversationExpanded(true);

      setHasRuntimeError(false);
      setChangeExplanation(null);
      setIsThinking(true);
      setIsStreaming(true);
      try {
        const profileBeforeTurn = profile;
        const actionProgressBeforeTurn = actionProgress;
        const latestVerifiedActionBeforeTurn = latestVerifiedAction;
        let profileRefreshPromise: ReturnType<typeof loadProfile> | null = null;
        let hasDecisionRelevantFeedback = false;
        const decisionChanges: DecisionChange[] = [];

        await streamMessage({
          conversationId,
          message,
          onChunk: (chunk) => {
            setIsThinking(false);

            /*
             * 后端在开始 Streaming 前已经完成 Profile 更新。
             * 因此首个 Chunk 到达时即可刷新 Workspace。
             */
            if (!profileRefreshPromise) {
              profileRefreshPromise = loadProfile();
            }

            setMessages((currentMessages) => {
              const assistantMessageExists = currentMessages.some(
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
          onDecisionRelevantFeedback: () => {
            hasDecisionRelevantFeedback = true;
          },
          onDecisionChange: (change) => {
            decisionChanges.push(change);
          },
        });

        const refreshedProfile = await (profileRefreshPromise ?? loadProfile());
        const shouldRefreshDecision = Boolean(
          refreshedProfile &&
          (profileBeforeTurn === null ||
            hasMeaningfulProfileChange(profileBeforeTurn, refreshedProfile)),
        );
        const hasDecisionChallenge = decisionChanges.some((change) =>
          change.causes.some(
            (cause) => cause.source === 'DECISION_CHALLENGE',
          ),
        );
        const hasVerificationOutcome = decisionChanges.some((change) =>
          change.causes.some(
            (cause) => cause.source === 'VERIFICATION_OUTCOME',
          ),
        );

        if (
          shouldRefreshDecision ||
          hasDecisionRelevantFeedback ||
          hasDecisionChallenge ||
          hasVerificationOutcome
        ) {
          const refreshed = await refreshDecision();
          if (refreshed && decisionChanges.length > 0) {
            setChangeExplanation(decisionChanges[0].explanation);
          }
        }
        await loadCandidate();
        const refreshedActionState = await loadActionProgress();
        const hasActionStateUpdate = refreshedActionState
          ? hasActionStateChanged(
              actionProgressBeforeTurn,
              latestVerifiedActionBeforeTurn,
              refreshedActionState.action_progress,
              refreshedActionState.latest_verified_action,
            )
          : false;

        if (
          shouldRefreshDecision ||
          hasDecisionRelevantFeedback ||
          hasDecisionChallenge ||
          hasVerificationOutcome ||
          hasActionStateUpdate
        ) {
          setIsConversationExpanded(false);
          requestAnimationFrame(() => {
            decisionSurfaceRef.current?.scrollIntoView({
              behavior: 'smooth',
              block: 'start',
            });
          });
        }
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
    [
      conversationId,
      isStreaming,
      loadActionProgress,
      loadCandidate,
      loadProfile,
      latestVerifiedAction,
      profile,
      refreshDecision,
      actionProgress,
    ],
  );

  useEffect(() => {
    if (!initialMessage || !conversationId || initialMessageSentRef.current) {
      return;
    }

    initialMessageSentRef.current = true;
    void sendConversationMessage(initialMessage);
  }, [conversationId, initialMessage, sendConversationMessage]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: 'auto',
      block: 'end',
    });
  }, [messages, isThinking]);

  const isInitialTurnStarting =
    Boolean(initialMessage) && messages.length === 1;

  return (
    <ConversationLayout
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
              <LivingState
                profile={profile}
                decision={decision}
                actionProgress={actionProgress}
                latestVerifiedAction={latestVerifiedAction}
                decisionSurfaceRef={decisionSurfaceRef}
              />
              <DecisionChangeExplanation explanation={changeExplanation} />
              <CandidateCard candidate={candidate} />

              <section className="mt-10 border-t border-white/[0.06] pt-5">
                <button
                  type="button"
                  aria-expanded={isConversationExpanded}
                  onClick={() => setIsConversationExpanded((value) => !value)}
                  className="flex w-full items-center justify-between gap-4 text-left"
                >
                  <span className="font-mono text-[10px] tracking-[0.16em] text-slate-600">
                    最近对话
                  </span>
                  <span className="text-xs text-slate-500">
                    {isConversationExpanded ? '收起' : '查看最近对话'}
                  </span>
                </button>

                {isConversationExpanded && (
                  <div className="mt-5">
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
                )}
              </section>
            </div>
          </div>

          <ConversationComposer
            disabled={isStreaming}
            onSubmit={(message) => {
              void sendConversationMessage(message);
            }}
            onListeningChange={setIsListening}
          />
        </section>

        <div className="hidden min-h-0 xl:block">
          <ProfileWorkspace profile={profile} isLoading={isProfileLoading} />
        </div>
      </div>
    </ConversationLayout>
  );
}

function CandidateCard({
  candidate,
}: {
  candidate: Property | null;
}) {
  if (!candidate) {
    return (
      <section
        aria-labelledby="candidate-title"
        className="mt-7 border-y border-white/[0.06] py-5"
      >
        <p
          id="candidate-title"
          className="font-mono text-[10px] tracking-[0.16em] text-blue-400"
        >
          候选房源
        </p>
        <h2 className="mt-2 text-lg font-medium text-slate-200">
          还没有候选房源
        </h2>
        <p className="mt-2 text-sm leading-6 text-slate-500">
          把你正在考虑的房源告诉 LiveOS。
        </p>
      </section>
    );
  }

  const propertyTitle = candidate.title?.trim() || '候选房源';
  const layout = [
    typeof candidate.bedrooms === 'number' ? `${candidate.bedrooms}室` : null,
    typeof candidate.bathrooms === 'number' ? `${candidate.bathrooms}卫` : null,
    typeof candidate.area === 'number' ? `${candidate.area}㎡` : null,
  ]
    .filter((value): value is string => Boolean(value))
    .join(' · ');

  return (
    <section
      aria-labelledby="candidate-title"
      className="mt-7 border-y border-white/[0.06] py-5"
    >
      <p className="font-mono text-[10px] tracking-[0.16em] text-blue-400">
        候选房源
      </p>
      <h2
        id="candidate-title"
        className="mt-2 truncate text-lg font-medium text-slate-200"
      >
        {propertyTitle}
      </h2>

      <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-sm text-slate-400">
        {typeof candidate.rent === 'number' && (
          <span>租金 ¥{candidate.rent.toLocaleString('zh-CN')} / 月</span>
        )}
        {typeof candidate.commute_minutes === 'number' && (
          <span>通勤 {candidate.commute_minutes} 分钟</span>
        )}
        {layout && <span>{layout}</span>}
        {candidate.district && <span>{candidate.district}</span>}
        {candidate.pet_friendly != null && (
          <span>{candidate.pet_friendly ? '可养宠物' : '不接受宠物'}</span>
        )}
      </div>
    </section>
  );
}

function DecisionChangeExplanation({
  explanation,
}: {
  explanation: string | null;
}) {
  if (!explanation) return null;

  return (
    <section
      aria-labelledby="decision-change-explanation"
      className="border-b border-white/[0.06] py-6"
    >
      <p
        id="decision-change-explanation"
        className="font-mono text-[10px] tracking-[0.16em] text-blue-400"
      >
        判断已更新
      </p>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
        {explanation} LiveOS 已根据这项变化重新评估当前方案。
      </p>
    </section>
  );
}

function CurrentProblem({ profile }: { profile: LivingProfile | null }) {
  const location = profile?.preferred_city || profile?.work_location;
  const title = location ? `${location}租房` : '当前居住问题';

  return (
    <section
      aria-labelledby="current-problem"
      className="border-b border-white/[0.06] pb-7"
    >
      <p
        id="current-problem"
        className="font-mono text-[10px] tracking-[0.16em] text-blue-400"
      >
        当前问题
      </p>
      <h1 className="mt-3 text-xl font-medium tracking-tight text-slate-200 sm:text-2xl">
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
  actionProgress,
  latestVerifiedAction,
  decisionSurfaceRef,
}: {
  profile: LivingProfile | null;
  decision: DecisionResult | null;
  actionProgress: CurrentActionProgress | null;
  latestVerifiedAction: LatestVerifiedAction | null;
  decisionSurfaceRef: RefObject<HTMLElement | null>;
}) {
  const isDecision = decision?.status === 'ready' && Boolean(decision.summary);
  const summaryParts = decision?.summary?.split(' 下一步：', 2) ?? [];
  const reason = decision?.reasons[0];
  const tradeOff = decision?.trade_offs[0];

  return (
    <section
      ref={decisionSurfaceRef}
      aria-labelledby="living-state"
      className="pt-9"
    >
      <p
        id="living-state"
        className="font-mono text-[10px] tracking-[0.16em] text-blue-400"
      >
        {isDecision ? '当前判断' : '正在形成判断'}
      </p>
      <h2 className="mt-2 text-2xl font-medium tracking-tight text-slate-100 sm:text-3xl">
        {isDecision ? '当前判断' : 'LiveOS 正在形成关于这件事的判断'}
      </h2>

      {isDecision ? (
        <div className="mt-6 space-y-6">
          <p className="max-w-4xl text-lg leading-8 text-slate-200 sm:text-xl">
            {summaryParts[0]}
          </p>
          <div className="space-y-4 border-y border-white/[0.06] py-5">
            {reason && <StateItem label="为什么这样判断" value={reason.description} />}
            {tradeOff && <StateItem label="需要注意" value={tradeOff.description} />}
          </div>
          <RealityProgress
            actionProgress={actionProgress}
            latestVerifiedAction={latestVerifiedAction}
          />
          {summaryParts[1] && (
            <div className="border border-blue-400/25 bg-blue-500/[0.07] px-5 py-4 sm:px-6">
              <p className="font-mono text-[10px] tracking-[0.16em] text-blue-300">
                下一步
              </p>
              <p className="mt-2 text-base leading-7 text-slate-100 sm:text-lg">
                → {summaryParts[1]}
              </p>
              {getActionProgressLabel(actionProgress?.status ?? null) && (
                <p className="mt-2 text-xs text-blue-200">
                  {getActionProgressLabel(actionProgress?.status ?? null)}
                </p>
              )}
            </div>
          )}
        </div>
      ) : decision?.status === 'waiting' ? (
        <div className="mt-5 max-w-3xl space-y-3 text-sm leading-6 text-slate-400">
          <p>{decision.summary || '我还不能给出可靠建议。'}</p>
          <p className="text-slate-600">目前还缺少足够信息或候选方案。</p>
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

function StateItem({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail?: string | null;
}) {
  return (
    <div className="border-l border-blue-500/30 pl-4">
      <p className="font-mono text-[10px] tracking-[0.12em] text-slate-600">
        {label}
      </p>
      <p className="mt-1 text-sm leading-6 text-slate-400">{value}</p>
      {detail && <p className="mt-1 text-xs text-blue-300">{detail}</p>}
    </div>
  );
}

function getActionProgressLabel(
  status: ActionProgressStatus | null,
): string | null {
  if (status === 'NOT_STARTED') return null;
  if (status === 'PLANNED') return '已计划';
  if (status === 'COMPLETED') return '已完成';
  if (status === 'ABANDONED') return '已放弃';
  return null;
}

function getVerificationOutcomeLabel(
  status: VerificationOutcomeStatus | null,
): string | null {
  if (status === 'CONFIRMED') return '✓ 已确认';
  if (status === 'DISCONFIRMED') return '× 已证伪';
  if (status === 'INCONCLUSIVE') return '— 暂未确认';
  return null;
}

function RealityProgress({
  actionProgress,
  latestVerifiedAction,
}: {
  actionProgress: CurrentActionProgress | null;
  latestVerifiedAction: LatestVerifiedAction | null;
}) {
  const currentProgress = getActionProgressLabel(actionProgress?.status ?? null);
  const currentOutcome = getVerificationOutcomeLabel(
    actionProgress?.outcome_status ?? null,
  );
  const latestOutcome = getVerificationOutcomeLabel(
    latestVerifiedAction?.outcome_status ?? null,
  );

  if (!currentProgress && !currentOutcome && !latestVerifiedAction) {
    return null;
  }

  return (
    <section aria-labelledby="reality-progress" className="space-y-4">
      <p
        id="reality-progress"
        className="font-mono text-[10px] tracking-[0.16em] text-blue-400"
      >
        现实进展
      </p>
      {currentProgress && (
        <div className="border-l border-white/15 pl-4">
          <p className="text-sm text-slate-300">当前行动</p>
          <p className="mt-1 text-sm text-slate-500">
            {currentProgress}
            {currentOutcome ? ` · ${currentOutcome}` : ''}
          </p>
        </div>
      )}
      {latestVerifiedAction && (
        <div className="border-l border-blue-400/35 pl-4">
          <p className="text-sm text-slate-300">已确认的现实</p>
          {latestOutcome && (
            <p className="mt-1 text-sm text-slate-400">{latestOutcome}</p>
          )}
          <div className="mt-2 space-y-1.5 text-sm leading-6 text-slate-500">
            {latestVerifiedAction.verification_evidence.map((evidence) => (
              <p key={`${evidence.field}-${evidence.statement}`}>
                {evidence.statement}
              </p>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function getUnderstandingCopy(profile: LivingProfile | null) {
  const location = profile?.work_location || profile?.preferred_city;
  const details = [
    location ? `你正在寻找${location}附近的居住方案。` : null,
    typeof profile?.budget === 'number'
      ? `预算约 ¥${profile.budget.toLocaleString('zh-CN')}`
      : null,
    profile?.family_size === 1 ? '倾向独立居住' : null,
    typeof profile?.commute_minutes === 'number'
      ? `通勤希望 ≤${profile.commute_minutes} 分钟`
      : null,
  ].filter(Boolean);

  return details.length > 0
    ? details.join('，')
    : 'LiveOS 正在根据当前对话理解你的需求。';
}
