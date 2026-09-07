'use client';

import { useCallback, useMemo, useState } from 'react';

import ConversationComposer from '@/features/conversation/components/ConversationComposer';
import AMapGround, { type GeographicProjection } from './AMapGround';

type ExperienceState =
  | 'FIRST_OPEN'
  | 'FOCUS_A'
  | 'FOCUS_B'
  | 'DUAL_FOCUS'
  | 'FOCUS_D'
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

const groundedLocations = [
  workAnchor.location,
  choices[1].location,
  choices[3].location,
].filter((location): location is GeographicLocation => Boolean(location));

export default function LivingMap() {
  const [projection, setProjection] = useState<GeographicProjection | null>(null);
  const [returnToLivingWorld, setReturnToLivingWorld] = useState<(() => void) | null>(null);
  const [userExploredCamera, setUserExploredCamera] = useState(false);
  const [mapZoom, setMapZoom] = useState<number | null>(null);
  const [focusedChoice, setFocusedChoice] = useState<'B' | 'D' | null>(null);
  const [bRealityChanged, setBRealityChanged] = useState(false);

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
  const currentExperienceState: ExperienceState = focusedChoice === 'B'
    ? 'FOCUS_B'
    : focusedChoice === 'D'
      ? 'FOCUS_D'
      : 'FIRST_OPEN';

  const projectedPositions = useMemo<Record<string, ScreenPosition>>(() => {
    if (!projection) return {};

    const nextPositions: Record<string, ScreenPosition> = {};
    if (workAnchor.location) {
      nextPositions.WORK = projection(workAnchor.location);
    }
    for (const choice of choices) {
      if ('location' in choice && choice.location) {
        nextPositions[choice.id] = projection(choice.location);
      }
    }
    return nextPositions;
  }, [projection]);

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
              className="world-object work-anchor"
              aria-label={`我的工作，${workAnchor.name}`}
            >
              <span className="object-mark">◎</span>
              <span className="object-kicker">我的工作</span>
              <span className="object-name">{workAnchor.name}</span>
            </div>
          </div>

          <div
            className={`absolute${projectedPositions.B ? '' : ' right-[8%] top-[46%] sm:right-[21%]'}`}
            style={projectedPositions.B ? positionStyle(projectedPositions.B) : undefined}
          >
            <ChoiceObject
              {...choices[1]}
              focused={focusedChoice === 'B' && !bRealityChanged}
              onFocus={
                bRealityChanged
                  ? undefined
                  : () => setFocusedChoice((current) => (current === 'B' ? null : 'B'))
              }
              realityChanged={bRealityChanged}
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
              {...choices[3]}
              focused={focusedChoice === 'D'}
              onFocus={() => setFocusedChoice((current) => (current === 'D' ? null : 'D'))}
              showLivingTime={showLivingTime}
            />
          </div>
        </section>

        <div aria-label="Relationship layer" className="pointer-events-none absolute inset-0 z-[1]" />
        <div aria-label="Meaning layer" className="pointer-events-none absolute inset-0 z-[1]" />

        <div className="absolute inset-x-0 bottom-0 z-20 px-5 pb-6 sm:px-10 sm:pb-8">
          <div className="mx-auto max-w-3xl">
            <ConversationComposer
              variant="ambient"
              onSubmit={(message) => {
                if (focusedChoice === 'B' && message.trim()) {
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
  onFocus,
}: LivingChoice & {
  focused?: boolean;
  onFocus?: () => void;
  realityChanged?: boolean;
  showLivingTime: boolean;
}) {
  const isQuiet = tone === 'quiet';
  const objectClassName = `world-object choice-object${isQuiet ? ' choice-object-quiet' : ''}`;

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
          showLivingTime={showLivingTime}
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
        showLivingTime={showLivingTime}
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
  showLivingTime,
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
  showLivingTime: boolean;
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
            夜间噪音较大
          </span>
          <span className="mt-1 text-[11px] font-medium tracking-[0.04em] text-slate-600">
            已不再适合
          </span>
        </>
      ) : showLivingTime ? (
        <span className="mt-1 font-mono text-[10px] font-medium tracking-[0.08em] text-slate-700">
          {livingTime}
        </span>
      ) : null}
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
