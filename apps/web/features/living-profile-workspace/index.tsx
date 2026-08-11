'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import {
  BriefcaseBusiness,
  Building2,
  Check,
  CircleDollarSign,
  House,
  Sparkles,
  Users,
} from 'lucide-react';

import AICore, {
  type AICoreState,
} from '@/features/ai-entry/components/AICore';
import { getLivingProfile, type LivingProfile } from '@/services/profile';

const UNKNOWN_VALUE = '仍在了解中';

const JOURNEY_STEPS = [
  '入口',
  '对话',
  '生活模型',
  '工作台',
  '详情',
  '对比',
  '决策',
  '记忆',
] as const;

interface ProfileField {
  label: string;
  value: string | number | boolean | null | undefined;
  understoodInsight: string;
  learningInsight: string;
  format?: (value: string | number | boolean) => string;
}

interface ProfileSection {
  title: string;
  description: string;
  icon: typeof BriefcaseBusiness;
  fields: ProfileField[];
}

function hasProfileValue(
  value: ProfileField['value'],
): value is string | number | boolean {
  if (typeof value === 'string') {
    return value.trim().length > 0;
  }

  return typeof value === 'number' || typeof value === 'boolean';
}

function formatProfileValue(field: ProfileField): string {
  if (!hasProfileValue(field.value)) {
    return UNKNOWN_VALUE;
  }

  return field.format ? field.format(field.value) : String(field.value);
}

function getProfileSections(profile: LivingProfile | null): ProfileSection[] {
  return [
    {
      title: '工作与通勤',
      description: '工作与日常通勤要求',
      icon: BriefcaseBusiness,
      fields: [
        {
          label: '工作地点',
          value: profile?.work_location,
          understoodInsight: '已了解到你的工作地点。',
          learningInsight: '希望继续了解你的工作地点。',
        },
        {
          label: '通勤要求',
          value: profile?.commute_minutes,
          understoodInsight: '已了解到你的通勤需求。',
          learningInsight: '希望继续了解你的通勤需求。',
          format: (value) => `${value} 分钟以内`,
        },
      ],
    },
    {
      title: '预算',
      description: '当前住房预算范围',
      icon: CircleDollarSign,
      fields: [
        {
          label: '月租预算',
          value: profile?.budget,
          understoodInsight: '已了解到你的租房预算。',
          learningInsight: '希望继续了解你的租房预算。',
          format: (value) => `$${Number(value).toLocaleString('en-US')}/月`,
        },
      ],
    },
    {
      title: '住房偏好',
      description: '理想住房的地点偏好',
      icon: House,
      fields: [
        {
          label: '意向城市',
          value: profile?.preferred_city,
          understoodInsight: '已了解到你的目标城市。',
          learningInsight: '希望继续了解你的目标城市。',
        },
      ],
    },
    {
      title: '家庭与生活方式',
      description: '家庭结构与生活方式',
      icon: Users,
      fields: [
        {
          label: '居住人数',
          value: profile?.family_size,
          understoodInsight: '已了解到你的居住人数。',
          learningInsight: '希望继续了解你的家庭居住人数。',
          format: (value) => `${value} 人`,
        },
        {
          label: '是否养宠物',
          value: profile?.has_pet,
          understoodInsight: '已了解到你的宠物生活情况。',
          learningInsight: '希望继续了解你的宠物生活情况。',
          format: (value) => (value === true ? '是' : '否'),
        },
      ],
    },
  ];
}

export default function LivingProfileWorkspace() {
  const searchParams = useSearchParams();
  const conversationId = searchParams.get('conversation_id') ?? '';
  const [profile, setProfile] = useState<LivingProfile | null>(null);
  const [isLoading, setIsLoading] = useState(Boolean(conversationId));
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    let isActive = true;

    async function loadProfile() {
      if (!conversationId) {
        setIsLoading(false);
        return;
      }

      setIsLoading(true);
      setHasError(false);

      try {
        const nextProfile = await getLivingProfile(conversationId);

        if (isActive) {
          setProfile(nextProfile);
        }
      } catch (error: unknown) {
        console.error('Failed to load living profile:', error);

        if (isActive) {
          setHasError(true);
          setProfile(null);
        }
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    }

    void loadProfile();

    return () => {
      isActive = false;
    };
  }, [conversationId]);

  const sections = useMemo(() => getProfileSections(profile), [profile]);
  const fields = sections.flatMap((section) => section.fields);
  const understoodCount = fields.filter((field) =>
    hasProfileValue(field.value),
  ).length;
  const unknownCount = fields.length - understoodCount;
  const conversationHref = conversationId
    ? `/conversation?conversation_id=${encodeURIComponent(conversationId)}`
    : '/conversation';
  const propertyHref = conversationId
    ? `/workspace/property?conversation_id=${encodeURIComponent(conversationId)}`
    : '/workspace/property';

  return (
    <main className="min-h-screen bg-[#050812] text-slate-100">
      <WorkspaceHeader
        conversationHref={conversationHref}
        coreState={
          hasError
            ? 'error'
            : isLoading
              ? 'understanding'
              : 'completed'
        }
      />

      <div className="runtime-flow min-h-[calc(100vh-72px)] bg-[radial-gradient(circle_at_top,rgba(68,82,164,0.12)_0,transparent_42%),radial-gradient(rgba(91,112,180,0.08)_1px,transparent_1px)] bg-[size:auto,28px_28px]">
        <div className="mx-auto w-full max-w-[1180px] px-5 py-10 sm:px-8 lg:py-14">
          <section className="flex flex-col justify-between gap-6 sm:flex-row sm:items-end">
            <div>
              <p className="font-mono text-xs tracking-[0.16em] text-blue-400">
                生活模型
              </p>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
                生活模型
              </h1>
              <p className="mt-3 text-base text-slate-500">
                AI 正在持续建立你的居住模型。
              </p>
            </div>
            <Link
              href={propertyHref}
              className="w-fit rounded-xl border border-blue-500/30 bg-blue-500/10 px-5 py-3 text-sm font-medium text-blue-300 transition hover:border-blue-400/50 hover:bg-blue-500/15"
            >
              进入房源工作台
            </Link>
          </section>

          {hasError && (
            <p
              role="alert"
              className="mt-6 rounded-xl border border-amber-400/20 bg-amber-400/5 px-4 py-3 text-sm text-amber-200"
            >
              当前资料暂时无法加载，以下内容将在连接恢复后更新。
            </p>
          )}

          <Overview
            isLoading={isLoading}
            understoodCount={understoodCount}
            unknownCount={unknownCount}
          />

          <section
            aria-label="生活模型领域"
            className="mt-8 grid gap-5 md:grid-cols-2"
          >
            {sections.map((section) => (
              <LivingSection
                key={section.title}
                section={section}
                isLoading={isLoading}
              />
            ))}
          </section>

          <AIInsightCard fields={fields} isLoading={isLoading} />
        </div>
      </div>
    </main>
  );
}

function WorkspaceHeader({
  conversationHref,
  coreState,
}: {
  conversationHref: string;
  coreState: AICoreState;
}) {
  return (
    <header className="border-b border-white/[0.06] bg-[#050812]/95">
      <div className="mx-auto flex h-[72px] max-w-[1480px] items-center gap-8 px-5 sm:px-8">
        <Link
          href="/"
          aria-label="返回 LiveOS 首页"
          className="flex shrink-0 items-center gap-2.5"
        >
          <AICore state={coreState} size="sm" />
          <span className="text-lg font-semibold tracking-tight">
            Live
            <span className="text-blue-500">OS</span>
          </span>
        </Link>

        <nav
          aria-label="LiveOS 决策旅程"
          className="hidden min-w-0 flex-1 items-center justify-center xl:flex"
        >
          {JOURNEY_STEPS.map((step, index) => {
            const stepNumber = index + 1;
            const isComplete = stepNumber < 3;
            const isCurrent = stepNumber === 3;

            return (
              <div key={step} className="flex items-center">
                <div
                  className={[
                    'flex items-center gap-2 text-sm',
                    isCurrent
                      ? 'font-medium text-slate-100'
                      : isComplete
                        ? 'text-blue-400'
                        : 'text-slate-600',
                  ].join(' ')}
                >
                  <span
                    className={[
                      'flex h-7 w-7 items-center justify-center rounded-full border text-xs',
                      isCurrent
                        ? 'border-blue-500 bg-blue-500 text-white'
                        : isComplete
                          ? 'border-blue-500/70 bg-blue-500/10'
                          : 'border-slate-800 bg-slate-900/70',
                    ].join(' ')}
                  >
                    {isComplete ? <Check size={14} /> : stepNumber}
                  </span>
                  <span>{step}</span>
                </div>

                {index < JOURNEY_STEPS.length - 1 && (
                  <span className="mx-3 h-px w-5 bg-slate-800" />
                )}
              </div>
            );
          })}
        </nav>

        <Link
          href={conversationHref}
          className="ml-auto rounded-xl border border-white/10 px-4 py-2 text-sm text-slate-400 transition hover:border-white/20 hover:text-slate-200"
        >
          返回对话
        </Link>
      </div>
    </header>
  );
}

function Overview({
  isLoading,
  understoodCount,
  unknownCount,
}: {
  isLoading: boolean;
  understoodCount: number;
  unknownCount: number;
}) {
  return (
    <section
      aria-labelledby="profile-overview-title"
      className="mt-10 rounded-2xl border border-white/[0.08] bg-[#0b1020]/90 p-6 shadow-[0_20px_60px_rgba(0,0,0,0.2)] sm:p-7"
    >
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-blue-500/20 bg-blue-500/10 text-blue-300">
          <Building2 size={19} />
        </span>
        <div>
          <h2
            id="profile-overview-title"
            className="font-medium text-slate-200"
          >
            居住模型概览
          </h2>
          <p className="mt-1 text-sm text-slate-500">当前居住模型完成度</p>
        </div>
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <OverviewMetric
          label="已理解"
          value={isLoading ? null : understoodCount}
          tone="blue"
        />
        <OverviewMetric
          label="仍需了解"
          value={isLoading ? null : unknownCount}
          tone="slate"
        />
      </div>
    </section>
  );
}

function OverviewMetric({
  label,
  value,
  tone,
}: {
  label: string;
  value: number | null;
  tone: 'blue' | 'slate';
}) {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-black/10 px-5 py-4">
      <p className="text-sm text-slate-500">{label}</p>
      {value === null ? (
        <div className="mt-3 h-8 w-16 animate-pulse rounded bg-white/[0.06]" />
      ) : (
        <p
          className={[
            'mt-2 font-mono text-3xl font-medium',
            tone === 'blue' ? 'text-blue-400' : 'text-slate-300',
          ].join(' ')}
        >
          {value}
          <span className="ml-2 text-sm font-normal text-slate-600">项</span>
        </p>
      )}
    </div>
  );
}

function LivingSection({
  section,
  isLoading,
}: {
  section: ProfileSection;
  isLoading: boolean;
}) {
  const Icon = section.icon;

  return (
    <article className="runtime-grow rounded-2xl border border-white/[0.08] bg-[#0b1020]/90 p-6 sm:p-7">
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/[0.08] bg-white/[0.03] text-slate-400">
          <Icon size={19} />
        </span>
        <div>
          <h2 className="font-medium text-slate-200">{section.title}</h2>
          <p className="mt-1 text-sm text-slate-600">{section.description}</p>
        </div>
      </div>

      <dl className="mt-6 divide-y divide-white/[0.06]">
        {section.fields.map((field) => (
          <div
            key={field.label}
            className="runtime-grow flex min-h-14 items-center justify-between gap-6 py-3 first:pt-0 last:pb-0"
          >
            <dt className="text-sm text-slate-500">{field.label}</dt>
            <dd className="text-right text-sm font-medium text-slate-300">
              {isLoading ? (
                <span className="block h-4 w-20 animate-pulse rounded bg-white/[0.06]" />
              ) : (
                formatProfileValue(field)
              )}
            </dd>
          </div>
        ))}
      </dl>
    </article>
  );
}

function AIInsightCard({
  fields,
  isLoading,
}: {
  fields: ProfileField[];
  isLoading: boolean;
}) {
  const understoodInsights = fields
    .filter((field) => hasProfileValue(field.value))
    .map((field) => field.understoodInsight);
  const learningInsights = fields
    .filter((field) => !hasProfileValue(field.value))
    .map((field) => field.learningInsight);
  const isEmpty = understoodInsights.length === 0;
  const isComplete = learningInsights.length === 0;

  return (
    <section
      aria-labelledby="ai-insight-title"
      className="runtime-grow mt-8 rounded-2xl border border-white/[0.08] bg-[#0b1020]/90 p-6 shadow-[0_20px_60px_rgba(0,0,0,0.2)] sm:p-7"
    >
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-violet-500/20 bg-violet-500/10 text-violet-300">
          <Sparkles size={19} />
        </span>
        <div>
          <h2 id="ai-insight-title" className="font-medium text-slate-200">
            AI 洞察
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            AI 对当前生活模型的理解
          </p>
        </div>
      </div>

      {isLoading ? (
        <div className="mt-6 space-y-3">
          <div className="h-4 w-3/4 animate-pulse rounded bg-white/[0.06]" />
          <div className="h-4 w-1/2 animate-pulse rounded bg-white/[0.06]" />
        </div>
      ) : isEmpty ? (
        <div className="mt-6 rounded-xl border border-white/[0.06] bg-black/10 px-5 py-5">
          <p className="text-sm font-medium text-slate-300">
            AI 还没有建立足够的生活模型。
          </p>
          <p className="mt-2 text-sm leading-6 text-slate-500">
            继续与 AI 对话后，这里会逐步展示它对你的理解。
          </p>
        </div>
      ) : isComplete ? (
        <div className="mt-6 rounded-xl border border-blue-500/15 bg-blue-500/[0.04] px-5 py-5">
          <p className="text-sm font-medium text-slate-300">
            生活模型已建立完成。
          </p>
          <p className="mt-2 text-sm leading-6 text-slate-500">
            后续新的对话仍会持续更新你的居住模型。
          </p>
        </div>
      ) : (
        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <InsightGroup
            title="已理解"
            items={understoodInsights}
            type="understood"
          />
          <InsightGroup
            title="希望继续了解"
            items={learningInsights}
            type="learning"
          />
        </div>
      )}
    </section>
  );
}

function InsightGroup({
  title,
  items,
  type,
}: {
  title: string;
  items: string[];
  type: 'understood' | 'learning';
}) {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-black/10 px-5 py-5">
      <h3
        className={
          type === 'understood'
            ? 'text-sm font-medium text-blue-300'
            : 'text-sm font-medium text-slate-400'
        }
      >
        {title}
      </h3>
      <ul className="mt-4 space-y-3">
        {items.map((item) => (
          <li
            key={item}
            className="flex gap-3 text-sm leading-6 text-slate-500"
          >
            <span
              aria-hidden="true"
              className={
                type === 'understood' ? 'text-blue-400' : 'text-slate-600'
              }
            >
              {type === 'understood' ? '✓' : '•'}
            </span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
