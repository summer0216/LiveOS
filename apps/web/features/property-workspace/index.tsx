'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import {
  Building2,
  Check,
  Clock3,
  House,
  MapPin,
  PawPrint,
  Ruler,
  WalletCards,
} from 'lucide-react';

import { getProperty, type Property } from '@/services/property';

const UNKNOWN_VALUE = '仍在了解中';

const JOURNEY_STEPS = [
  '入口',
  '对话',
  '画像',
  '工作台',
  '详情',
  '对比',
  '决策',
  '记忆',
] as const;

interface PropertyField {
  label: string;
  value: string | number | boolean | null | undefined;
  icon: typeof MapPin;
  format?: (value: string | number | boolean) => string;
}

function hasPropertyValue(
  value: PropertyField['value'],
): value is string | number | boolean {
  if (typeof value === 'string') {
    return value.trim().length > 0;
  }

  return typeof value === 'number' || typeof value === 'boolean';
}

function formatPropertyValue(field: PropertyField): string {
  if (!hasPropertyValue(field.value)) {
    return UNKNOWN_VALUE;
  }

  return field.format ? field.format(field.value) : String(field.value);
}

function formatLayout(property: Property): string {
  const parts = [
    typeof property.bedrooms === 'number' ? `${property.bedrooms} 室` : null,
    typeof property.bathrooms === 'number' ? `${property.bathrooms} 卫` : null,
  ].filter((part): part is string => part !== null);

  return parts.length > 0 ? parts.join(' · ') : UNKNOWN_VALUE;
}

function getPropertyFields(property: Property): PropertyField[] {
  return [
    {
      label: '区域',
      value: property.district,
      icon: MapPin,
    },
    {
      label: '月租',
      value: property.rent,
      icon: WalletCards,
      format: (value) => `$${Number(value).toLocaleString('en-US')}/月`,
    },
    {
      label: '面积',
      value: property.area,
      icon: Ruler,
      format: (value) => `${value} ㎡`,
    },
    {
      label: '通勤时间',
      value: property.commute_minutes,
      icon: Clock3,
      format: (value) => `${value} 分钟`,
    },
    {
      label: '宠物友好',
      value: property.pet_friendly,
      icon: PawPrint,
      format: (value) => (value === true ? '是' : '否'),
    },
  ];
}

export default function PropertyWorkspace() {
  const searchParams = useSearchParams();
  const conversationId = searchParams.get('conversation_id') ?? '';
  const [property, setProperty] = useState<Property | null>(null);
  const [isLoading, setIsLoading] = useState(Boolean(conversationId));
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    let isActive = true;

    async function loadProperty() {
      if (!conversationId) {
        setIsLoading(false);
        return;
      }

      setIsLoading(true);
      setHasError(false);

      try {
        const nextProperty = await getProperty(conversationId);

        if (isActive) {
          setProperty(nextProperty);
        }
      } catch (error: unknown) {
        console.error('Failed to load property:', error);

        if (isActive) {
          setHasError(true);
          setProperty(null);
        }
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    }

    void loadProperty();

    return () => {
      isActive = false;
    };
  }, [conversationId]);

  const properties = useMemo(() => (property ? [property] : []), [property]);
  const profileHref = conversationId
    ? `/workspace/profile?conversation_id=${encodeURIComponent(conversationId)}`
    : '/workspace/profile';

  return (
    <main className="min-h-screen bg-[#050812] text-slate-100">
      <WorkspaceHeader profileHref={profileHref} />

      <div className="min-h-[calc(100vh-72px)] bg-[radial-gradient(circle_at_top,rgba(68,82,164,0.12)_0,transparent_42%),radial-gradient(rgba(91,112,180,0.08)_1px,transparent_1px)] bg-[size:auto,28px_28px]">
        <div className="mx-auto w-full max-w-[1180px] px-5 py-10 sm:px-8 lg:py-14">
          <section>
            <p className="font-mono text-xs tracking-[0.16em] text-blue-400">
              PROPERTY WORKSPACE
            </p>
            <h1 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
              Property Workspace
            </h1>
            <p className="mt-3 max-w-xl text-base leading-7 text-slate-500">
              管理你的候选房源，AI 将基于这些房源完成后续分析。
            </p>
          </section>

          {hasError && (
            <p
              role="alert"
              className="mt-6 rounded-xl border border-amber-400/20 bg-amber-400/5 px-4 py-3 text-sm text-amber-200"
            >
              候选房源暂时无法加载，请稍后重试。
            </p>
          )}

          <PropertyOverview count={properties.length} isLoading={isLoading} />

          <section aria-labelledby="property-list-title" className="mt-8">
            <div className="flex items-end justify-between gap-4">
              <div>
                <h2
                  id="property-list-title"
                  className="text-lg font-medium text-slate-200"
                >
                  Property List
                </h2>
                <p className="mt-1 text-sm text-slate-600">
                  当前保存的候选房源
                </p>
              </div>
              {!isLoading && (
                <span className="font-mono text-xs text-slate-600">
                  {properties.length} 套
                </span>
              )}
            </div>

            {isLoading ? (
              <PropertyListLoading />
            ) : properties.length === 0 ? (
              <PropertyEmptyState />
            ) : (
              <div className="mt-5 grid gap-5 md:grid-cols-2">
                {properties.map((item, index) => (
                  <PropertyCard
                    key={`${item.title ?? 'property'}-${index}`}
                    property={item}
                  />
                ))}
              </div>
            )}
          </section>
        </div>
      </div>
    </main>
  );
}

function WorkspaceHeader({ profileHref }: { profileHref: string }) {
  return (
    <header className="border-b border-white/[0.06] bg-[#050812]/95">
      <div className="mx-auto flex h-[72px] max-w-[1480px] items-center gap-8 px-5 sm:px-8">
        <Link
          href="/"
          aria-label="返回 LiveOS 首页"
          className="flex shrink-0 items-center gap-2.5"
        >
          <span className="h-9 w-9 rounded-full bg-[radial-gradient(circle_at_35%_30%,#8d78ff_0,#5265dd_48%,#1a275a_100%)] shadow-[0_0_24px_rgba(93,91,255,0.35)]" />
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
            const isComplete = stepNumber < 4;
            const isCurrent = stepNumber === 4;

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
          href={profileHref}
          className="ml-auto rounded-xl border border-white/10 px-4 py-2 text-sm text-slate-400 transition hover:border-white/20 hover:text-slate-200"
        >
          返回 Living Profile
        </Link>
      </div>
    </header>
  );
}

function PropertyOverview({
  count,
  isLoading,
}: {
  count: number;
  isLoading: boolean;
}) {
  return (
    <section
      aria-labelledby="property-overview-title"
      className="mt-10 rounded-2xl border border-white/[0.08] bg-[#0b1020]/90 p-6 shadow-[0_20px_60px_rgba(0,0,0,0.2)] sm:p-7"
    >
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-blue-500/20 bg-blue-500/10 text-blue-300">
          <Building2 size={19} />
        </span>
        <div>
          <h2
            id="property-overview-title"
            className="font-medium text-slate-200"
          >
            Overview
          </h2>
          <p className="mt-1 text-sm text-slate-500">候选房源</p>
        </div>
      </div>

      <div className="mt-6 rounded-xl border border-white/[0.06] bg-black/10 px-5 py-4">
        <p className="text-sm text-slate-500">候选房源</p>
        {isLoading ? (
          <div className="mt-3 h-8 w-16 animate-pulse rounded bg-white/[0.06]" />
        ) : (
          <p className="mt-2 font-mono text-3xl font-medium text-blue-400">
            {count}
            <span className="ml-2 text-sm font-normal text-slate-600">套</span>
          </p>
        )}
      </div>
    </section>
  );
}

function PropertyEmptyState() {
  return (
    <div className="mt-5 flex min-h-72 flex-col items-center justify-center rounded-2xl border border-dashed border-white/[0.1] bg-[#0b1020]/70 px-6 text-center">
      <span className="flex h-14 w-14 items-center justify-center rounded-2xl border border-white/[0.08] bg-white/[0.03] text-slate-500">
        <House size={24} />
      </span>
      <h3 className="mt-6 text-lg font-medium text-slate-300">
        你还没有添加候选房源。
      </h3>
      <p className="mt-3 max-w-sm text-sm leading-6 text-slate-500">
        开始添加第一套房源，AI 将帮助你完成后续分析。
      </p>
    </div>
  );
}

function PropertyListLoading() {
  return (
    <div className="mt-5 grid gap-5 md:grid-cols-2">
      <div className="h-80 animate-pulse rounded-2xl border border-white/[0.06] bg-[#0b1020]/90" />
    </div>
  );
}

function PropertyCard({ property }: { property: Property }) {
  const fields = getPropertyFields(property);
  const title = hasPropertyValue(property.title)
    ? property.title.trim()
    : UNKNOWN_VALUE;

  return (
    <article className="rounded-2xl border border-white/[0.08] bg-[#0b1020]/90 p-6 shadow-[0_20px_60px_rgba(0,0,0,0.16)] sm:p-7">
      <div>
        <p className="font-mono text-xs tracking-[0.12em] text-blue-400">
          CANDIDATE PROPERTY
        </p>
        <h3 className="mt-3 text-xl font-medium text-slate-200">{title}</h3>
        <p className="mt-2 text-sm text-slate-500">
          户型：{formatLayout(property)}
        </p>
      </div>

      <dl className="mt-6 grid gap-3 sm:grid-cols-2">
        {fields.map((field) => {
          const Icon = field.icon;

          return (
            <div
              key={field.label}
              className="rounded-xl border border-white/[0.06] bg-black/10 px-4 py-3"
            >
              <dt className="flex items-center gap-2 text-xs text-slate-600">
                <Icon size={14} />
                {field.label}
              </dt>
              <dd className="mt-2 text-sm font-medium text-slate-300">
                {formatPropertyValue(field)}
              </dd>
            </div>
          );
        })}
      </dl>
    </article>
  );
}
