'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';

import ConversationComposer from '@/features/conversation/components/ConversationComposer';
import AMapGround, {
  type GeographicProjection,
} from '@/features/living-map/AMapGround';
import { createClientId } from '@/lib/createClientId';
import { sendMessage } from '@/services/chat';
import { getDecisionGeography } from '@/services/decisionGeography';
import { getProperties, type Property } from '@/services/property';
import { getLivingProfile, type LivingProfile } from '@/services/profile';

type ScenePhase = 'empty' | 'forming' | 'formed';
type LocationResolution = 'pending' | 'resolved' | 'fallback';

const FIRST_OPEN_CENTER = { lng: 113.93, lat: 22.54 };
const NO_FIT_LOCATIONS: readonly { lng: number; lat: number }[] = [];

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

  useEffect(() => {
    let settled = false;
    const fallbackToDefaultContext = () => {
      if (settled) return;
      settled = true;
      console.info('[First Open] Current Geographic Reality unavailable; using default context');
      setLocationResolution('fallback');
    };

    if (!navigator.geolocation) {
      fallbackToDefaultContext();
      return;
    }

    const fallbackTimer = window.setTimeout(fallbackToDefaultContext, 10500);
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
        fallbackToDefaultContext();
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
    ]).then(([nextProfile, nextProperties]) => {
      if (!active) return;
      setProperties(nextProperties);
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

  const handleSubmit = useCallback(async (message: string) => {
    const currentConversationId = conversationId || createClientId();

    setPhase('forming');
    setWorkVisible(false);
    setDecisionWorldActive(false);
    try {
      await sendMessage(currentConversationId, message, currentLocation);
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
        reorient?.(
          { lng: decisionGeography.lng, lat: decisionGeography.lat },
          10.5,
        );
      } else if (currentLocation) {
        reorient?.(currentLocation, 12.5);
      }
    } catch (error: unknown) {
      console.error('Failed to form First Reality:', error);
      setPhase('empty');
    }
  }, [conversationId, currentLocation, reorient]);

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
  const workPosition = useMemo(
    () => groundedWork && projection ? projection(groundedWork) : null,
    [groundedWork, projection],
  );
  const groundedChoices = useMemo(
    () => properties.filter(
      (property) => property.geographic_status === 'GROUNDED'
        && typeof property.lng === 'number'
        && typeof property.lat === 'number',
    ),
    [properties],
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
  const initialCenter = currentLocation ?? FIRST_OPEN_CENTER;

  return (
    <main className="relative min-h-screen overflow-hidden bg-[#eef2ed] text-slate-950">
      {locationResolution !== 'pending' && (
        <AMapGround
          fitLocations={NO_FIT_LOCATIONS}
          initialCenter={initialCenter}
          initialZoom={12.5}
          presentation={decisionWorldActive ? 'active' : 'quiet'}
          onProjectionReady={handleProjectionReady}
          onCameraReady={handleCameraReady}
        />
      )}
      <div
        aria-hidden="true"
        className={
          'pointer-events-none absolute inset-0 z-[1] transition-[background] duration-1000 ease-out motion-reduce:transition-none ' +
          (decisionWorldActive
            ? 'bg-transparent'
            : worldHasFormed
            ? 'bg-[radial-gradient(ellipse_at_center,rgba(238,242,237,0.62)_0%,rgba(238,242,237,0.46)_30%,rgba(238,242,237,0.24)_58%,rgba(238,242,237,0.08)_80%,transparent_100%)]'
            : 'bg-[radial-gradient(ellipse_at_center,rgba(238,242,237,0.78)_0%,rgba(238,242,237,0.62)_30%,rgba(238,242,237,0.35)_58%,rgba(238,242,237,0.12)_80%,transparent_100%)]')
        }
      />
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
              className="world-object work-anchor"
              aria-label={'我的工作，' + groundedWork.displayIdentity}
            >
              <span className="object-mark">◎</span>
              <span className="object-kicker mt-2">我的工作</span>
              <span className="object-name mt-2">
                {groundedWork.displayIdentity}
              </span>
            </div>
          </div>
        )}

        {groundedChoices.map((property) => {
          const position = choicePositions[property.id];
          if (!position) return null;
          return (
            <div
              key={property.id}
              className="absolute -translate-x-1/2 -translate-y-1/2 text-center"
              style={{ left: position.x, top: position.y }}
            >
              <div
                className="world-object choice-object"
                aria-label={property.title ?? '未命名选择'}
              >
                <span className="object-mark">●</span>
                <span className="object-name mt-2">
                  {property.title ?? '未命名选择'}
                </span>
                {typeof property.commute_minutes === 'number' && (
                  <span className="mt-1 font-mono text-[10px] font-medium tracking-[0.08em] text-slate-700">
                    {property.commute_minutes} min
                  </span>
                )}
              </div>
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
