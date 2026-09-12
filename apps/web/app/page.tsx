'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';

import ConversationComposer from '@/features/conversation/components/ConversationComposer';
import AMapGround, {
  type GeographicProjection,
} from '@/features/living-map/AMapGround';
import { createClientId } from '@/lib/createClientId';
import { streamMessage } from '@/services/chat';
import {
  getDecisionGeography,
  type DecisionGeography,
} from '@/services/decisionGeography';
import { getProperties, type Property } from '@/services/property';
import { getLivingProfile, type LivingProfile } from '@/services/profile';

type ScenePhase = 'empty' | 'forming' | 'formed';
type LocationResolution = 'pending' | 'resolved' | 'unknown';

function formatGeographicIdentity(
  identity: string,
  precision: LivingProfile['geographic_precision'],
) {
  if (precision !== 'AREA') return identity;

  const administrativeAreas = identity.match(
    /[^省市区县旗]+(?:省|市|区|县|旗)/g,
  );
  return administrativeAreas?.at(-1) ?? identity;
}

export default function HomePage() {
  const searchParams = useSearchParams();
  const [conversationId, setConversationId] = useState(
    () => searchParams.get('conversation_id') ?? '',
  );
  const [profile, setProfile] = useState<LivingProfile | null>(null);
  const [properties, setProperties] = useState<Property[]>([]);
  const [projection, setProjection] = useState<GeographicProjection | null>(null);
  const [phase, setPhase] = useState<ScenePhase>('empty');
  const [workVisible, setWorkVisible] = useState(false);
  const [locationResolution, setLocationResolution] = useState<LocationResolution>('pending');
  const [currentLocation, setCurrentLocation] = useState<{ lng: number; lat: number } | null>(null);
  const [reorient, setReorient] = useState<
    ((center: { lng: number; lat: number }, zoom: number) => void) | null
  >(null);
  const [decisionWorldActive, setDecisionWorldActive] = useState(false);
  const [restoredDecisionGeography, setRestoredDecisionGeography] = useState<
    DecisionGeography | null | undefined
  >(undefined);
  const [focusedPropertyId, setFocusedPropertyId] = useState<string | null>(null);

  useEffect(() => {
    let settled = false;
    const markLocationUnknown = () => {
      if (settled) return;
      settled = true;
      console.info('[First Open] Current Geographic Reality unavailable; remaining unknown');
      setLocationResolution('unknown');
    };

    if (!navigator.geolocation) {
      markLocationUnknown();
      return;
    }

    const fallbackTimer = window.setTimeout(markLocationUnknown, 10500);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        if (settled) return;
        settled = true;
        window.clearTimeout(fallbackTimer);
        console.info('[First Open] Current Geographic Reality resolved', {
          lng: position.coords.longitude,
          lat: position.coords.latitude,
        });
        setCurrentLocation({
          lng: position.coords.longitude,
          lat: position.coords.latitude,
        });
        setLocationResolution('resolved');
      },
      () => {
        window.clearTimeout(fallbackTimer);
        markLocationUnknown();
      },
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 },
    );

    return () => {
      settled = true;
      window.clearTimeout(fallbackTimer);
    };
  }, []);

  useEffect(() => {
    if (!conversationId) return;

    let active = true;
    void Promise.all([
      getLivingProfile(conversationId),
      getProperties(conversationId),
      getDecisionGeography(conversationId),
    ]).then(([nextProfile, nextProperties, decisionGeography]) => {
      if (!active) return;
      setProperties(nextProperties);
      setRestoredDecisionGeography(decisionGeography);
      if (
        decisionGeography?.intent_established
        && decisionGeography.status === 'GROUNDED'
        && typeof decisionGeography.lng === 'number'
        && typeof decisionGeography.lat === 'number'
      ) {
        setDecisionWorldActive(true);
      }
      if (!nextProfile) return;
      setProfile(nextProfile);
      if (nextProfile.geographic_status === 'GROUNDED') {
        setPhase('formed');
        setWorkVisible(true);
      }
    }).catch((error: unknown) => {
      console.error('Failed to restore First Reality:', error);
    });

    return () => {
      active = false;
    };
  }, [conversationId]);

  const handleProjectionReady = useCallback(
    (nextProjection: GeographicProjection) => {
      setProjection(() => nextProjection);
    },
    [],
  );

  const handleCameraReady = useCallback(
    (nextReorient: (center: { lng: number; lat: number }, zoom: number) => void) => {
      setReorient(() => nextReorient);
    },
    [],
  );

  const clearChoiceFocus = useCallback(() => {
    setFocusedPropertyId(null);
  }, []);

  const groundedWork = useMemo(
    () => profile?.geographic_status === 'GROUNDED'
      && typeof profile.lng === 'number'
      && typeof profile.lat === 'number'
      ? {
          lng: profile.lng,
          lat: profile.lat,
          identity: profile.geographic_identity ?? profile.work_location ?? '',
          displayIdentity: formatGeographicIdentity(
            profile.geographic_identity ?? profile.work_location ?? '',
            profile.geographic_precision,
          ),
        }
      : null,
    [profile],
  );
  const groundedChoices = useMemo(
    () => properties.filter(
      (property): property is Property & { lng: number; lat: number } =>
        property.geographic_status === 'GROUNDED'
        && typeof property.lng === 'number'
        && typeof property.lat === 'number',
    ),
    [properties],
  );
  const housingFitLocations = useMemo(
    () => groundedWork && groundedChoices.length > 0
      ? [
          { lng: groundedWork.lng, lat: groundedWork.lat },
          ...groundedChoices.map((property) => ({
            lng: property.lng,
            lat: property.lat,
          })),
        ]
      : [],
    [groundedChoices, groundedWork],
  );
  const hasHousingDecisionExtent = housingFitLocations.length >= 2;

  useEffect(() => {
    if (
      !reorient
      || hasHousingDecisionExtent
      || restoredDecisionGeography?.conversation_id !== conversationId
      || !restoredDecisionGeography?.intent_established
      || restoredDecisionGeography.status !== 'GROUNDED'
      || typeof restoredDecisionGeography.lng !== 'number'
      || typeof restoredDecisionGeography.lat !== 'number'
    ) {
      return;
    }

    reorient(
      {
        lng: restoredDecisionGeography.lng,
        lat: restoredDecisionGeography.lat,
      },
      10.5,
    );
  }, [
    conversationId,
    hasHousingDecisionExtent,
    reorient,
    restoredDecisionGeography,
  ]);

  const handleSubmit = useCallback(async (message: string) => {
    const currentConversationId = conversationId || createClientId();

    setPhase('forming');
    setWorkVisible(false);
    setDecisionWorldActive(false);
    try {
      let markWorldStateReady: (() => void) | undefined;
      const worldStateReady = new Promise<void>((resolve) => {
        markWorldStateReady = resolve;
      });
      const chatCompletion = streamMessage({
        conversationId: currentConversationId,
        message,
        currentGeographicReality: currentLocation,
        onChunk: () => {},
        onWorldStateReady: () => markWorldStateReady?.(),
      });

      await Promise.race([
        worldStateReady,
        chatCompletion.then(() => undefined),
      ]);
      const [nextProfile, nextProperties, decisionGeography] = await Promise.all([
        getLivingProfile(currentConversationId),
        getProperties(currentConversationId),
        getDecisionGeography(currentConversationId),
      ]);
      if (!nextProfile) {
        throw new Error('First Reality profile was not persisted.');
      }
      if (!conversationId) {
        setConversationId(currentConversationId);
        window.history.replaceState(
          window.history.state,
          '',
          '/?conversation_id=' + encodeURIComponent(currentConversationId),
        );
      }
      setProfile(nextProfile);
      setProperties(nextProperties);
      setPhase(nextProfile?.geographic_status === 'GROUNDED' ? 'formed' : 'empty');
      if (nextProfile?.geographic_status === 'GROUNDED') {
        requestAnimationFrame(() => setWorkVisible(true));
      }
      if (
        decisionGeography?.intent_established
        && decisionGeography.status === 'GROUNDED'
        && typeof decisionGeography.lng === 'number'
        && typeof decisionGeography.lat === 'number'
      ) {
        setDecisionWorldActive(true);
        const hasGroundedWork = nextProfile.geographic_status === 'GROUNDED'
          && typeof nextProfile.lng === 'number'
          && typeof nextProfile.lat === 'number';
        const hasGroundedChoices = nextProperties.some(
          (property) => property.geographic_status === 'GROUNDED'
            && typeof property.lng === 'number'
            && typeof property.lat === 'number',
        );
        if (!hasGroundedWork || !hasGroundedChoices) {
          reorient?.(
            { lng: decisionGeography.lng, lat: decisionGeography.lat },
            10.5,
          );
        }
      } else if (currentLocation) {
        reorient?.(currentLocation, 12.5);
      }
      await chatCompletion;
    } catch (error: unknown) {
      console.error('Failed to form First Reality:', error);
      setPhase('empty');
    }
  }, [conversationId, currentLocation, reorient]);

  const workPosition = useMemo(
    () => groundedWork && projection ? projection(groundedWork) : null,
    [groundedWork, projection],
  );
  const choicePositions = useMemo(
    () => groundedChoices.reduce<Record<string, { x: number; y: number }>>(
      (positions, property) => {
        if (projection && property.lng !== null && property.lat !== null) {
          positions[property.id] = projection({
            lng: property.lng,
            lat: property.lat,
          });
        }
        return positions;
      },
      {},
    ),
    [groundedChoices, projection],
  );
  const worldHasFormed = phase === 'formed' && Boolean(groundedWork);
  const restoredDecisionCenter = useMemo(
    () => restoredDecisionGeography?.conversation_id === conversationId
      && restoredDecisionGeography.intent_established
      && restoredDecisionGeography.status === 'GROUNDED'
      && typeof restoredDecisionGeography.lng === 'number'
      && typeof restoredDecisionGeography.lat === 'number'
      ? {
          lng: restoredDecisionGeography.lng,
          lat: restoredDecisionGeography.lat,
        }
      : null,
    [conversationId, restoredDecisionGeography],
  );
  const initialMapCenter = restoredDecisionCenter ?? currentLocation;
  return (
    <main className="relative min-h-screen overflow-hidden bg-[#eef2ed] text-slate-950">
      {initialMapCenter
        && (restoredDecisionCenter || locationResolution === 'resolved') && (
        <AMapGround
          fitLocations={housingFitLocations}
          initialCenter={initialMapCenter}
          initialZoom={restoredDecisionCenter ? 10.5 : 12.5}
          onProjectionReady={handleProjectionReady}
          onCameraReady={handleCameraReady}
          onMapClick={clearChoiceFocus}
        />
      )}
      <section
        aria-label={worldHasFormed ? 'First Reality' : 'Empty Living World'}
        className={`relative z-10 min-h-screen ${decisionWorldActive ? 'pointer-events-none' : ''}`}
      >
        <h1
          className={
            'absolute left-1/2 top-1/2 max-w-xl -translate-x-1/2 -translate-y-[62%] text-center text-[clamp(1.85rem,4vw,3.4rem)] font-normal leading-[1.15] tracking-[-0.025em] text-slate-900/90 transition-opacity duration-500 ease-out motion-reduce:transition-none ' +
            (phase === 'empty' && !decisionWorldActive
              ? 'opacity-100'
              : 'pointer-events-none opacity-0')
          }
        >
          你的生活，
          <br />
          从哪里开始？
        </h1>

        {groundedWork && workPosition && (
          <div
            className={
              'absolute -translate-x-1/2 -translate-y-1/2 text-center transition-opacity delay-300 duration-700 ease-out motion-reduce:delay-0 motion-reduce:transition-none ' +
              (workVisible ? 'opacity-100' : 'opacity-0')
            }
            style={{ left: workPosition.x, top: workPosition.y }}
          >
            <div
              className={`world-object work-anchor ${focusedPropertyId ? 'world-object-context' : ''}`}
              aria-label={[
                '我的工作',
                groundedWork.displayIdentity,
                typeof profile?.commute_minutes === 'number'
                  ? `通勤不超过 ${profile.commute_minutes} 分钟`
                  : null,
                typeof profile?.budget === 'number'
                  ? `预算约 ${profile.budget} 元`
                  : null,
              ].filter(Boolean).join('，')}
            >
              <span className="object-mark">◎</span>
              <span className="object-kicker mt-2">我的工作</span>
              <span className="object-name mt-2">
                {groundedWork.displayIdentity}
              </span>
              {typeof profile?.commute_minutes === 'number' && (
                <span className="mt-2 font-mono text-[11px] font-medium tracking-[0.04em] text-slate-700">
                  ≤ {profile.commute_minutes}min 通勤
                </span>
              )}
              {typeof profile?.budget === 'number' && (
                <span className="mt-1 font-mono text-[11px] font-medium tracking-[0.04em] text-slate-700">
                  ≈ ¥{profile.budget} 预算
                </span>
              )}
            </div>
          </div>
        )}

        {groundedChoices.map((property) => {
          const position = choicePositions[property.id];
          if (!position) return null;
          const focused = focusedPropertyId === property.id;
          const receded = focusedPropertyId !== null && !focused;
          const commuteMode = property.commute_mode === 'WALKING'
            ? '步行'
            : property.commute_mode === 'PUBLIC_TRANSIT'
              ? '公共交通'
              : null;
          return (
            <div
              key={property.id}
              className={`absolute -translate-x-1/2 -translate-y-1/2 text-center ${focused ? 'z-20' : 'z-10'}`}
              style={{ left: position.x, top: position.y }}
            >
              <button
                type="button"
                className={`world-object choice-object pointer-events-auto appearance-none border-0 bg-transparent p-0 text-center focus:outline-none ${focused ? 'choice-object-focused' : ''} ${receded ? 'world-object-receded' : ''}`}
                aria-label={`聚焦 ${property.title ?? '未命名选择'}`}
                aria-pressed={focused}
                onClick={(event) => {
                  event.stopPropagation();
                  setFocusedPropertyId(property.id);
                }}
              >
                <span className="object-mark">{focused ? '◉' : '●'}</span>
                {focused && (
                  <span className="object-kicker mt-2">可能的家</span>
                )}
                <span className="object-name mt-2">
                  {property.title ?? '未命名选择'}
                </span>
                {typeof property.commute_minutes === 'number' && (
                  <span className="mt-1 font-mono text-[10px] font-medium tracking-[0.08em] text-slate-700">
                    {focused ? '到工作地点 ' : ''}{property.commute_minutes} min
                    {focused && commuteMode ? ` · ${commuteMode}` : ''}
                  </span>
                )}
              </button>
            </div>
          );
        })}
      </section>
      <div className="absolute inset-x-0 bottom-0 z-20 px-5 pb-5 sm:px-10 sm:pb-8">
        <div className="mx-auto max-w-3xl">
          <ConversationComposer
            disabled={phase === 'forming'}
            variant="ambient"
            placeholder="告诉 LiveOS，你现在最想解决的生活问题……"
            onSubmit={(message) => {
              void handleSubmit(message);
            }}
            onListeningChange={() => undefined}
          />
        </div>
      </div>
    </main>
  );
}
