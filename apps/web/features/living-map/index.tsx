'use client';

import { useCallback, useMemo, useState } from 'react';

import ConversationComposer from '@/features/conversation/components/ConversationComposer';
import AMapGround, { type GeographicProjection } from './AMapGround';

type ExperienceState =
  | 'FIRST_OPEN'
  | 'FOCUS_A'
  | 'FOCUS_B'
  | 'FOCUS_C'
  | 'DUAL_FOCUS'
  | 'FOCUS_D'
  | 'COMPARE_BD'
  | 'REALITY_RESOLVE'
  | 'SEE_AGAIN';

export type GeographicPrecision = 'AREA' | 'PLACE' | 'UNKNOWN';

export interface GeographicLocation {
  lng: number;
  lat: number;
}

interface LivingWorldObject {
  id: string;
  name: string;
  geographicPrecision: GeographicPrecision;
  location?: GeographicLocation;
}

interface LivingChoice extends LivingWorldObject {
  id: 'A' | 'B' | 'C' | 'D';
  tone: 'active' | 'quiet';
  livingTime: string;
  meaning?: string;
  possibleHomeRent?: string;
  possibleHomeUnknown?: string;
  possibleHomeAction?: string;
}

interface ScreenPosition {
  x: number;
  y: number;
}

const CITY_SCALE_ZOOM_THRESHOLD = 13;

const workAnchor: LivingWorldObject = {
  id: 'WORK',
  name: '南山科技园',
  geographicPrecision: 'AREA',
  location: {
    lng: 113.947,
    lat: 22.541,
  },
};

const choices = [
  {
    id: 'A',
    name: '科苑花园',
    tone: 'active',
    geographicPrecision: 'UNKNOWN',
    livingTime: '24 min',
    meaning: '当前领先',
    possibleHomeRent: '¥5,800/月',
  },
  {
    id: 'B',
    name: '后海公寓',
    tone: 'active',
    geographicPrecision: 'PLACE',
    livingTime: '31 min',
    location: {
      lng: 113.929757,
      lat: 22.510291,
    },
    possibleHomeRent: '¥5,200/月',
    possibleHomeUnknown: '夜间噪音 ?',
    possibleHomeAction: '晚上实地待20分钟 →',
  },
  {
    id: 'C',
    name: '西丽居',
    tone: 'quiet',
    geographicPrecision: 'UNKNOWN',
    livingTime: '42 min',
  },
  {
    id: 'D',
    name: '宝安中心',
    tone: 'active',
    geographicPrecision: 'AREA',
    livingTime: '~25 min ?',
    location: {
      lng: 113.88604,
      lat: 22.55653,
    },
  },
] as const satisfies readonly LivingChoice[];

const A_GROUNDING_CLARIFICATION =
  '深圳市南山区科丰路1号科技园五十八区科苑花园58区（西门）';
const A_CONFIRMED_LOCATION: GeographicLocation = {
  lng: 113.950953,
  lat: 22.548949,
};

export default function LivingMap() {
  const [projection, setProjection] = useState<GeographicProjection | null>(null);
  const [returnToLivingWorld, setReturnToLivingWorld] = useState<(() => void) | null>(null);
  const [userExploredCamera, setUserExploredCamera] = useState(false);
  const [mapZoom, setMapZoom] = useState<number | null>(null);
  const [focusedChoice, setFocusedChoice] = useState<LivingChoice['id'] | null>(null);
  const [bRealityChanged, setBRealityChanged] = useState(false);
  const [dRealityChanged, setDRealityChanged] = useState(false);
  const [aResolved, setAResolved] = useState(false);
  const [comparisonActive, setComparisonActive] = useState(false);

  const handleProjectionReady = useCallback((nextProjection: GeographicProjection) => {
    setProjection(() => nextProjection);
  }, []);

  const handleReturnToLivingWorldReady = useCallback((action: (() => void) | null) => {
    setReturnToLivingWorld(() => action);
  }, []);

  const handleUserExploredCameraChange = useCallback((explored: boolean) => {
    setUserExploredCamera(explored);
  }, []);

  const handleZoomChange = useCallback((zoom: number) => {
    setMapZoom(zoom);
  }, []);

  const showLivingTime = mapZoom === null || mapZoom >= CITY_SCALE_ZOOM_THRESHOLD;
  const currentExperienceState: ExperienceState = comparisonActive
    ? 'COMPARE_BD'
    : focusedChoice
      ? (`FOCUS_${focusedChoice}` as ExperienceState)
      : 'FIRST_OPEN';
  const livingChoices = useMemo<readonly LivingChoice[]>(
    () => choices.map((choice) => (
      choice.id === 'A' && aResolved
        ? {
            ...choice,
            geographicPrecision: 'PLACE',
            location: A_CONFIRMED_LOCATION,
          }
        : choice
    )),
    [aResolved],
  );
  const groundedLocations = useMemo(
    () => [
      workAnchor.location,
      ...livingChoices.flatMap((choice) => (
        choice.location ? [choice.location] : []
      )),
    ].filter((location): location is GeographicLocation => Boolean(location)),
    [livingChoices],
  );
  const unresolvedChoices = livingChoices.filter((choice) => !choice.location);

  const projectedPositions = useMemo<Record<string, ScreenPosition>>(() => {
    if (!projection) return {};

    const nextPositions: Record<string, ScreenPosition> = {};
    if (workAnchor.location) {
      nextPositions.WORK = projection(workAnchor.location);
    }
    for (const choice of livingChoices) {
      if (choice.location) {
        nextPositions[choice.id] = projection(choice.location);
      }
    }
    return nextPositions;
  }, [livingChoices, projection]);

  return (
    <main
      data-experience-state={currentExperienceState}
      className="flex min-h-screen flex-col overflow-hidden bg-[#050812] text-slate-100"
    >
      <WorldCanvas>
        <GeographicGround
          fitLocations={groundedLocations}
          onProjectionReady={handleProjectionReady}
          onReturnToLivingWorldReady={handleReturnToLivingWorldReady}
          onUserExploredCameraChange={handleUserExploredCameraChange}
          onZoomChange={handleZoomChange}
        />

        {returnToLivingWorld && userExploredCamera && (
          <button
            type="button"
            onClick={returnToLivingWorld}
            aria-label="回到我的生活世界"
            title="回到我的生活世界"
            className="absolute right-5 top-5 z-30 flex h-9 w-9 items-center justify-center rounded-full border border-slate-300/80 bg-white/90 text-lg leading-none text-slate-800 shadow-sm backdrop-blur-sm transition hover:bg-white focus:outline-none focus:ring-2 focus:ring-slate-400/60"
          >
            ⌖
          </button>
        )}

        <section aria-label="生活世界对象" className="relative z-10 h-full">
          <div
            className={`absolute -translate-x-1/2 text-center${
              projectedPositions.WORK ? '' : ' left-1/2 top-[17%]'
            }`}
            style={projectedPositions.WORK ? positionStyle(projectedPositions.WORK) : undefined}
          >
            <div
              className={`world-object work-anchor${
                comparisonActive ? ' world-object-context' : ''
              }`}
              aria-label={`我的工作，${workAnchor.name}`}
            >
              <span className="object-mark">◎</span>
              <span className="object-kicker">我的工作</span>
              <span className="object-name">{workAnchor.name}</span>
            </div>
          </div>

          {projectedPositions.A && (
            <div className="absolute" style={positionStyle(projectedPositions.A)}>
              <ChoiceObject
                {...livingChoices[0]}
                focused={focusedChoice === 'A'}
                onFocus={() => {
                  setComparisonActive(false);
                  setFocusedChoice((current) => (current === 'A' ? null : 'A'));
                }}
                receded={comparisonActive}
                showLivingTime={showLivingTime}
              />
            </div>
          )}

          <div
            className={`absolute${projectedPositions.B ? '' : ' right-[8%] top-[46%] sm:right-[21%]'}`}
            style={projectedPositions.B ? positionStyle(projectedPositions.B) : undefined}
          >
            <ChoiceObject
              {...livingChoices[1]}
              focused={focusedChoice === 'B' && !bRealityChanged}
              onFocus={
                bRealityChanged
                  ? undefined
                  : () => {
                      setComparisonActive(false);
                      setFocusedChoice((current) => (current === 'B' ? null : 'B'));
                    }
              }
              realityChanged={bRealityChanged}
              realityPrimary="夜间噪音较大"
              realitySecondary="已不再适合"
              compareAttention={comparisonActive}
              compareMeaning={comparisonActive ? '通勤已知' : undefined}
              showLivingTime={showLivingTime}
            />
          </div>
          <div
            className={`absolute -translate-x-1/2${
              projectedPositions.D ? '' : ' left-1/2 top-[73%]'
            }`}
            style={projectedPositions.D ? positionStyle(projectedPositions.D) : undefined}
          >
            <ChoiceObject
              {...livingChoices[3]}
              focused={focusedChoice === 'D' && !dRealityChanged}
              onFocus={
                dRealityChanged
                  ? undefined
                  : () => {
                      setComparisonActive(false);
                      setFocusedChoice((current) => (current === 'D' ? null : 'D'));
                    }
              }
              realityChanged={dRealityChanged}
              realityPrimary="80 min"
              realitySecondary="已不再适合"
              compareAttention={comparisonActive}
              compareMeaning={comparisonActive ? '仍需确认' : undefined}
              showLivingTime={showLivingTime}
            />
          </div>
        </section>

        <div aria-label="Relationship layer" className="pointer-events-none absolute inset-0 z-[1]">
          {comparisonActive && projectedPositions.B && projectedPositions.D && (
            <svg
              aria-hidden="true"
              className="absolute inset-0 h-full w-full"
              preserveAspectRatio="none"
            >
              <line
                className="compare-relationship"
                x1={projectedPositions.B.x + 8}
                y1={projectedPositions.B.y + 8}
                x2="61%"
                y2="48%"
                vectorEffect="non-scaling-stroke"
              />
              <line
                className="compare-relationship"
                x1={projectedPositions.D.x + 8}
                y1={projectedPositions.D.y + 8}
                x2="39%"
                y2="48%"
                vectorEffect="non-scaling-stroke"
              />
            </svg>
          )}
        </div>
        <div aria-label="Meaning layer" className="pointer-events-none absolute inset-0 z-[1]">
          {comparisonActive && (
            <div
              aria-label="B 与 D 的生活差异"
              className="compare-meaning absolute left-1/2 top-[48%] -translate-x-1/2 -translate-y-1/2 text-center text-slate-950"
            >
              <p className="inline-flex items-center gap-3 font-mono text-[13px] font-medium tracking-[0.08em] text-blue-950/80">
                <span>B</span>
                <span aria-hidden="true">↔</span>
                <span>D</span>
              </p>
              <p className="mt-3 text-[clamp(1.15rem,2vw,1.45rem)] font-semibold leading-tight tracking-[-0.02em]">
                D 可能通勤更短
              </p>
              <p className="my-1.5 font-mono text-sm font-medium text-slate-500">↕</p>
              <p className="text-[clamp(1.05rem,1.8vw,1.3rem)] font-medium leading-tight tracking-[-0.015em] text-slate-800">
                但这个优势仍需确认
              </p>
            </div>
          )}
        </div>

        <div className="absolute inset-x-0 bottom-0 z-20 px-5 pb-6 sm:px-10 sm:pb-8">
          <div className="mx-auto max-w-3xl">
            {unresolvedChoices.length > 0 && (
              <p className="mb-3 max-w-lg rounded-xl border border-slate-400/35 bg-white/82 px-4 py-3 text-sm font-semibold leading-5 tracking-[0.01em] text-slate-800 shadow-[0_8px_24px_rgba(15,23,42,0.08)] backdrop-blur-md sm:px-5">
                没有找到「{unresolvedChoices.map((choice) => choice.name).join('」和「')}」对应的可靠地理位置，请提供更详细的地址、小区名称或附近地点。
              </p>
            )}
            <ConversationComposer
              variant="ambient"
              onSubmit={(message) => {
                if (!aResolved && message.trim() === A_GROUNDING_CLARIFICATION) {
                  setAResolved(true);
                  return;
                }
                const normalizedMessage = message
                  .normalize('NFKC')
                  .replace(/\s+/g, '')
                  .toUpperCase();
                const normalizedIntent = normalizedMessage.replace(/[，,。.!！“”"'‘’]/g, '');
                if (
                  !bRealityChanged
                  && !dRealityChanged
                  && (
                    normalizedMessage === '比较一下B和D'
                    || normalizedMessage === '对比B和D'
                  )
                ) {
                  setFocusedChoice(null);
                  setComparisonActive(true);
                  return;
                }
                if (
                  comparisonActive
                  && normalizedIntent === 'D实际通勤要80分钟我接受不了'
                ) {
                  setDRealityChanged(true);
                  setComparisonActive(false);
                  setFocusedChoice(null);
                  return;
                }
                if (focusedChoice === 'B' && message.trim()) {
                  setComparisonActive(false);
                  setBRealityChanged(true);
                  setFocusedChoice(null);
                }
              }}
              onListeningChange={() => undefined}
            />
          </div>
        </div>
      </WorldCanvas>
    </main>
  );
}

function WorldCanvas({ children }: { children: React.ReactNode }) {
  return (
    <section
      aria-label="Living World Canvas"
      className="relative min-h-screen flex-1 overflow-hidden"
    >
      {children}
    </section>
  );
}

function positionStyle(position: ScreenPosition): React.CSSProperties {
  return {
    left: `${position.x}px`,
    top: `${position.y}px`,
  };
}

function GeographicGround({
  fitLocations,
  onProjectionReady,
  onReturnToLivingWorldReady,
  onUserExploredCameraChange,
  onZoomChange,
}: {
  fitLocations: readonly GeographicLocation[];
  onProjectionReady: (projection: GeographicProjection) => void;
  onReturnToLivingWorldReady: (action: (() => void) | null) => void;
  onUserExploredCameraChange: (explored: boolean) => void;
  onZoomChange: (zoom: number) => void;
}) {
  return (
    <AMapGround
      fitLocations={fitLocations}
      onProjectionReady={onProjectionReady}
      onReturnToLivingWorldReady={onReturnToLivingWorldReady}
      onUserExploredCameraChange={onUserExploredCameraChange}
      onZoomChange={onZoomChange}
    />
  );
}

function ChoiceObject({
  id,
  name,
  tone,
  livingTime,
  showLivingTime,
  possibleHomeRent,
  possibleHomeUnknown,
  possibleHomeAction,
  focused = false,
  realityChanged = false,
  realityPrimary,
  realitySecondary,
  compareAttention = false,
  compareMeaning,
  receded = false,
  onFocus,
}: LivingChoice & {
  focused?: boolean;
  onFocus?: () => void;
  realityChanged?: boolean;
  realityPrimary?: string;
  realitySecondary?: string;
  compareAttention?: boolean;
  compareMeaning?: string;
  receded?: boolean;
  showLivingTime: boolean;
}) {
  const isQuiet = tone === 'quiet';
  const objectClassName = [
    'world-object choice-object',
    isQuiet ? 'choice-object-quiet' : '',
    compareAttention ? 'choice-object-compare' : '',
    receded ? 'world-object-receded' : '',
  ].filter(Boolean).join(' ');

  if (!onFocus) {
    return (
      <div className={objectClassName}>
        <ChoiceObjectContent
          focused={focused}
          id={id}
          isQuiet={isQuiet}
          livingTime={livingTime}
          name={name}
          possibleHomeRent={possibleHomeRent}
          possibleHomeUnknown={possibleHomeUnknown}
          possibleHomeAction={possibleHomeAction}
          realityChanged={realityChanged}
          realityPrimary={realityPrimary}
          realitySecondary={realitySecondary}
          showLivingTime={showLivingTime}
          compareMeaning={compareMeaning}
        />
      </div>
    );
  }

  return (
    <button
      type="button"
      className={`${objectClassName} appearance-none border-0 bg-transparent p-0 text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400/60`}
      onClick={onFocus}
      aria-pressed={focused}
      aria-label={`${focused ? '取消聚焦' : '聚焦'} ${id} ${name}`}
    >
      <ChoiceObjectContent
        focused={focused}
        id={id}
        isQuiet={isQuiet}
        livingTime={livingTime}
        name={name}
        possibleHomeRent={possibleHomeRent}
        possibleHomeUnknown={possibleHomeUnknown}
        possibleHomeAction={possibleHomeAction}
        realityChanged={realityChanged}
        realityPrimary={realityPrimary}
        realitySecondary={realitySecondary}
        showLivingTime={showLivingTime}
        compareMeaning={compareMeaning}
      />
    </button>
  );
}

function ChoiceObjectContent({
  focused,
  id,
  isQuiet,
  livingTime,
  name,
  possibleHomeRent,
  possibleHomeUnknown,
  possibleHomeAction,
  realityChanged,
  realityPrimary,
  realitySecondary,
  showLivingTime,
  compareMeaning,
}: {
  focused: boolean;
  id: LivingChoice['id'];
  isQuiet: boolean;
  livingTime: string;
  name: string;
  possibleHomeRent?: string;
  possibleHomeUnknown?: string;
  possibleHomeAction?: string;
  realityChanged: boolean;
  realityPrimary?: string;
  realitySecondary?: string;
  showLivingTime: boolean;
  compareMeaning?: string;
}) {
  return (
    <>
      <div className="flex items-center gap-2">
        <span className="object-mark">{realityChanged || isQuiet ? '○' : focused ? '◉' : '●'}</span>
        <span className="object-kicker">{id}</span>
      </div>
      <span className="object-name mt-2">{name}</span>
      {realityChanged ? (
        <>
          <span className="mt-1 text-[11px] font-medium tracking-[0.04em] text-slate-700">
            {realityPrimary}
          </span>
          <span className="mt-1 text-[11px] font-medium tracking-[0.04em] text-slate-600">
            {realitySecondary}
          </span>
        </>
      ) : showLivingTime ? (
        <span className="mt-1 font-mono text-[10px] font-medium tracking-[0.08em] text-slate-700">
          {livingTime}
        </span>
      ) : null}
      {!realityChanged && compareMeaning && (
        <span className="compare-object-meaning mt-1 text-[11px] font-semibold tracking-[0.04em]">
          {compareMeaning}
        </span>
      )}
      {!realityChanged && focused && possibleHomeRent && (
        <span className="mt-1 font-mono text-[11px] font-semibold tracking-[0.04em] text-slate-800">
          {possibleHomeRent}
        </span>
      )}
      {!realityChanged && focused && possibleHomeUnknown && (
        <span className="mt-2 text-[11px] font-medium tracking-[0.04em] text-slate-600">
          {possibleHomeUnknown}
          <span className="ml-1 text-slate-500">仍需确认</span>
        </span>
      )}
      {!realityChanged && focused && possibleHomeAction && (
        <span className="mt-2 text-[11px] font-medium tracking-[0.04em] text-slate-700">
          {possibleHomeAction}
        </span>
      )}
    </>
  );
}
