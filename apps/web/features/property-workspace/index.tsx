'use client';

import { useEffect, useState, type FormEvent } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import {
  Building2,
  Check,
  Clock3,
  House,
  MapPin,
  PawPrint,
  Plus,
  Ruler,
  Trash2,
  WalletCards,
} from 'lucide-react';

import {
  createProperty,
  deleteProperty,
  getProperties,
  type Property,
  type PropertyInput,
} from '@/services/property';

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

interface PropertyFormValues {
  title: string;
  district: string;
  rent: string;
  area: string;
  bedrooms: string;
  bathrooms: string;
  commuteMinutes: string;
  petFriendly: boolean;
}

const EMPTY_FORM_VALUES: PropertyFormValues = {
  title: '',
  district: '',
  rent: '',
  area: '',
  bedrooms: '',
  bathrooms: '',
  commuteMinutes: '',
  petFriendly: false,
};

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

function parseOptionalNumber(value: string): number | null {
  return value.trim() === '' ? null : Number(value);
}

function createPropertyInput(values: PropertyFormValues): PropertyInput {
  return {
    title: values.title.trim() || null,
    district: values.district.trim() || null,
    rent: parseOptionalNumber(values.rent),
    area: parseOptionalNumber(values.area),
    bedrooms: parseOptionalNumber(values.bedrooms),
    bathrooms: parseOptionalNumber(values.bathrooms),
    commute_minutes: parseOptionalNumber(values.commuteMinutes),
    pet_friendly: values.petFriendly,
  };
}

export default function PropertyWorkspace() {
  const searchParams = useSearchParams();
  const conversationId = searchParams.get('conversation_id') ?? '';
  const [properties, setProperties] = useState<Property[]>([]);
  const [isLoading, setIsLoading] = useState(Boolean(conversationId));
  const [loadError, setLoadError] = useState<string | null>(null);
  const [operationError, setOperationError] = useState<string | null>(null);
  const [deletingPropertyId, setDeletingPropertyId] = useState<string | null>(
    null,
  );
  const [isAdding, setIsAdding] = useState(false);

  useEffect(() => {
    let isActive = true;

    async function loadProperty() {
      if (!conversationId) {
        setLoadError('缺少 conversation_id，无法管理候选房源。');
        setIsLoading(false);
        return;
      }

      setIsLoading(true);
      setLoadError(null);

      try {
        const nextProperties = await getProperties(conversationId);

        if (isActive) {
          setProperties(nextProperties);
        }
      } catch (error: unknown) {
        console.error('Failed to load properties:', error);

        if (isActive) {
          setLoadError('候选房源加载失败，请稍后重试。');
          setProperties([]);
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

  const profileHref = conversationId
    ? `/workspace/profile?conversation_id=${encodeURIComponent(conversationId)}`
    : '/workspace/profile';
  const decisionHref = conversationId
    ? `/workspace/decision?conversation_id=${encodeURIComponent(conversationId)}`
    : '/workspace/decision';

  return (
    <main className="min-h-screen bg-[#050812] text-slate-100">
      <WorkspaceHeader profileHref={profileHref} />

      <div className="min-h-[calc(100vh-72px)] bg-[radial-gradient(circle_at_top,rgba(68,82,164,0.12)_0,transparent_42%),radial-gradient(rgba(91,112,180,0.08)_1px,transparent_1px)] bg-[size:auto,28px_28px]">
        <div className="mx-auto w-full max-w-[1180px] px-5 py-10 sm:px-8 lg:py-14">
          <section className="flex flex-col justify-between gap-6 sm:flex-row sm:items-end">
            <div>
              <p className="font-mono text-xs tracking-[0.16em] text-blue-400">
                PROPERTY WORKSPACE
              </p>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
                Property Workspace
              </h1>
              <p className="mt-3 max-w-xl text-base leading-7 text-slate-500">
                管理你的候选房源，AI 将基于这些房源完成后续分析。
              </p>
            </div>
            <Link
              href={decisionHref}
              className="w-fit rounded-xl border border-blue-500/30 bg-blue-500/10 px-5 py-3 text-sm font-medium text-blue-300 transition hover:border-blue-400/50 hover:bg-blue-500/15"
            >
              进入 AI Decision
            </Link>
          </section>

          {loadError && (
            <p
              role="alert"
              className="mt-6 rounded-xl border border-amber-400/20 bg-amber-400/5 px-4 py-3 text-sm text-amber-200"
            >
              {loadError}
            </p>
          )}

          {operationError && (
            <p
              role="alert"
              className="mt-6 rounded-xl border border-red-400/20 bg-red-400/5 px-4 py-3 text-sm text-red-200"
            >
              {operationError}
            </p>
          )}

          <PropertyOverview
            count={loadError ? null : properties.length}
            isLoading={isLoading}
          />

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
              <div className="flex items-center gap-3">
                {!isLoading && !loadError && (
                  <span className="font-mono text-xs text-slate-600">
                    {properties.length} 套
                  </span>
                )}
                <button
                  type="button"
                  disabled={
                    isLoading ||
                    isAdding ||
                    Boolean(loadError) ||
                    !conversationId
                  }
                  onClick={() => {
                    setOperationError(null);
                    setIsAdding(true);
                  }}
                  className="flex items-center gap-2 rounded-xl border border-blue-500/30 bg-blue-500/10 px-4 py-2.5 text-sm font-medium text-blue-300 transition hover:border-blue-400/50 hover:bg-blue-500/15 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Plus size={16} />
                  Add Property
                </button>
              </div>
            </div>

            {isAdding && (
              <PropertyForm
                onCancel={() => {
                  setOperationError(null);
                  setIsAdding(false);
                }}
                onSave={async (property) => {
                  if (!conversationId) {
                    setOperationError(
                      '缺少 conversation_id，无法添加候选房源。',
                    );
                    return false;
                  }

                  setOperationError(null);

                  try {
                    const createdProperty = await createProperty(
                      conversationId,
                      property,
                    );
                    setProperties((currentProperties) => [
                      ...currentProperties,
                      createdProperty,
                    ]);
                    setIsAdding(false);
                    return true;
                  } catch (error: unknown) {
                    console.error('Failed to create property:', error);
                    setOperationError('候选房源保存失败，请稍后重试。');
                    return false;
                  }
                }}
              />
            )}

            {isLoading ? (
              <PropertyListLoading />
            ) : loadError ? (
              <PropertyLoadError />
            ) : properties.length === 0 ? (
              <PropertyEmptyState
                onAdd={() => {
                  setIsAdding(true);
                }}
                isAdding={isAdding}
              />
            ) : (
              <div className="mt-5 grid gap-5 md:grid-cols-2">
                {properties.map((item) => (
                  <PropertyCard
                    key={item.id}
                    property={item}
                    isDeleting={deletingPropertyId === item.id}
                    onDelete={async () => {
                      setOperationError(null);
                      setDeletingPropertyId(item.id);

                      try {
                        await deleteProperty(item.id);
                        setProperties((currentProperties) =>
                          currentProperties.filter(
                            (currentProperty) => currentProperty.id !== item.id,
                          ),
                        );
                      } catch (error: unknown) {
                        console.error('Failed to delete property:', error);
                        setOperationError('候选房源删除失败，请稍后重试。');
                      } finally {
                        setDeletingPropertyId(null);
                      }
                    }}
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
  count: number | null;
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
        ) : count === null ? (
          <p className="mt-2 font-mono text-lg font-medium text-amber-200">
            无法读取
          </p>
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

function PropertyEmptyState({
  onAdd,
  isAdding,
}: {
  onAdd: () => void;
  isAdding: boolean;
}) {
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
      <button
        type="button"
        disabled={isAdding}
        onClick={onAdd}
        className="mt-6 flex items-center gap-2 rounded-xl border border-blue-500/30 bg-blue-500/10 px-5 py-3 text-sm font-medium text-blue-300 transition hover:border-blue-400/50 hover:bg-blue-500/15 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <Plus size={16} />
        添加第一套房源
      </button>
    </div>
  );
}

function PropertyLoadError() {
  return (
    <div className="mt-5 flex min-h-52 items-center justify-center rounded-2xl border border-dashed border-amber-400/20 bg-amber-400/[0.03] px-6 text-center">
      <p className="text-sm text-amber-200">候选房源加载失败，请稍后重试。</p>
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

export function PropertyCard({
  property,
  onDelete,
  isDeleting = false,
}: {
  property: Property;
  onDelete?: () => void | Promise<void>;
  isDeleting?: boolean;
}) {
  const fields = getPropertyFields(property);
  const title = hasPropertyValue(property.title)
    ? property.title.trim()
    : UNKNOWN_VALUE;

  return (
    <article className="rounded-2xl border border-white/[0.08] bg-[#0b1020]/90 p-6 shadow-[0_20px_60px_rgba(0,0,0,0.16)] sm:p-7">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-mono text-xs tracking-[0.12em] text-blue-400">
            CANDIDATE PROPERTY
          </p>
          <h3 className="mt-3 text-xl font-medium text-slate-200">{title}</h3>
          <p className="mt-2 text-sm text-slate-500">
            户型：{formatLayout(property)}
          </p>
        </div>
        {onDelete && (
          <button
            type="button"
            disabled={isDeleting}
            onClick={onDelete}
            className="flex shrink-0 items-center gap-2 rounded-xl border border-red-400/20 bg-red-400/5 px-3 py-2 text-xs text-red-300 transition hover:border-red-400/40 hover:bg-red-400/10 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Trash2 size={14} />
            {isDeleting ? 'Deleting…' : 'Delete'}
          </button>
        )}
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

function PropertyForm({
  onSave,
  onCancel,
}: {
  onSave: (property: PropertyInput) => Promise<boolean>;
  onCancel: () => void;
}) {
  const [values, setValues] = useState<PropertyFormValues>(EMPTY_FORM_VALUES);
  const [isSaving, setIsSaving] = useState(false);

  function updateValue(
    field: keyof PropertyFormValues,
    value: string | boolean,
  ) {
    setValues((currentValues) => ({
      ...currentValues,
      [field]: value,
    }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSaving(true);

    try {
      await onSave(createPropertyInput(values));
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <form
      onSubmit={submit}
      className="mt-5 rounded-2xl border border-blue-500/20 bg-[#0b1020]/90 p-6 shadow-[0_20px_60px_rgba(0,0,0,0.16)] sm:p-7"
    >
      <div>
        <p className="font-mono text-xs tracking-[0.12em] text-blue-400">
          NEW PROPERTY
        </p>
        <h3 className="mt-3 text-xl font-medium text-slate-200">
          New Property Form
        </h3>
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <PropertyTextInput
          label="标题"
          value={values.title}
          onChange={(value) => {
            updateValue('title', value);
          }}
        />
        <PropertyTextInput
          label="区域"
          value={values.district}
          onChange={(value) => {
            updateValue('district', value);
          }}
        />
        <PropertyNumberInput
          label="租金"
          value={values.rent}
          onChange={(value) => {
            updateValue('rent', value);
          }}
        />
        <PropertyNumberInput
          label="面积"
          value={values.area}
          onChange={(value) => {
            updateValue('area', value);
          }}
        />
        <PropertyNumberInput
          label="卧室"
          value={values.bedrooms}
          onChange={(value) => {
            updateValue('bedrooms', value);
          }}
        />
        <PropertyNumberInput
          label="卫生间"
          value={values.bathrooms}
          onChange={(value) => {
            updateValue('bathrooms', value);
          }}
        />
        <PropertyNumberInput
          label="通勤时间"
          value={values.commuteMinutes}
          onChange={(value) => {
            updateValue('commuteMinutes', value);
          }}
        />
        <label className="flex min-h-[70px] items-center justify-between rounded-xl border border-white/[0.08] bg-black/10 px-4 py-3">
          <span>
            <span className="block text-sm text-slate-400">宠物友好</span>
            <span className="mt-1 block text-xs text-slate-600">
              是否允许宠物入住
            </span>
          </span>
          <input
            type="checkbox"
            checked={values.petFriendly}
            onChange={(event) => {
              updateValue('petFriendly', event.target.checked);
            }}
            className="h-4 w-4 accent-blue-500"
          />
        </label>
      </div>

      <div className="mt-6 flex justify-end gap-3">
        <button
          type="button"
          disabled={isSaving}
          onClick={onCancel}
          className="rounded-xl border border-white/10 px-5 py-2.5 text-sm text-slate-400 transition hover:border-white/20 hover:text-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={isSaving}
          className="rounded-xl bg-blue-500 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-blue-400 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isSaving ? 'Saving…' : 'Save'}
        </button>
      </div>
    </form>
  );
}

function PropertyTextInput({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label>
      <span className="mb-2 block text-sm text-slate-500">{label}</span>
      <input
        type="text"
        value={value}
        onChange={(event) => {
          onChange(event.target.value);
        }}
        className="w-full rounded-xl border border-white/[0.08] bg-black/10 px-4 py-3 text-sm text-slate-200 transition outline-none placeholder:text-slate-700 focus:border-blue-500/40"
      />
    </label>
  );
}

function PropertyNumberInput({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label>
      <span className="mb-2 block text-sm text-slate-500">{label}</span>
      <input
        type="number"
        value={value}
        onChange={(event) => {
          onChange(event.target.value);
        }}
        className="w-full rounded-xl border border-white/[0.08] bg-black/10 px-4 py-3 text-sm text-slate-200 transition outline-none placeholder:text-slate-700 focus:border-blue-500/40"
      />
    </label>
  );
}
