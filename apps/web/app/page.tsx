'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';

import ConversationComposer from '@/features/conversation/components/ConversationComposer';
import PossibleLifeProjection from '@/features/living-map/PossibleLifeProjection';
import AMapGround, {
  type GeographicProjection,
} from '@/features/living-map/AMapGround';
import { createClientId } from '@/lib/createClientId';
import { focusedHomeViewport } from '@/lib/focusedHomeViewport';
import {
  decisionGeographyFingerprint,
  isGroundedDecisionGeography,
  shouldApplyObservedDecisionGeography,
} from '@/lib/decisionGeographyState';
import { streamMessage } from '@/services/chat';
import {
  getDecisionGeography,
  type DecisionGeography,
} from '@/services/decisionGeography';
import {
  acquireExternalRent,
  establishDailyGrocery,
  establishPlaceContext,
  executePublicRentAction,
  formLivingMeaning,
  getProperties,
  type Property,
} from '@/services/property';
import { getLivingProfile, type LivingProfile } from '@/services/profile';

type ScenePhase = 'empty' | 'forming' | 'formed';
type LocationResolution = 'pending' | 'resolved' | 'unknown';
type PendingAction = {
  propertyId: string;
  type: 'CONFIRM_RENT';
  status: 'PENDING';
};

type BudgetMeaning = '预算内' | '超预算' | null;

function deriveBudgetMeaning(
  budget: number | null | undefined,
  property: Pick<Property, 'rent' | 'rent_source'>,
): BudgetMeaning {
  if (
    typeof budget !== 'number'
    || typeof property.rent !== 'number'
    || !['USER_CONFIRMED_REALITY', 'USER_PROVIDED', 'EXTERNAL_SOURCE'].includes(property.rent_source ?? '')
  ) {
    return null;
  }

  return property.rent <= budget ? '预算内' : '超预算';
}

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

function formatAreaWorkIdentity(userValue: string, groundedIdentity: string) {
  const city = groundedIdentity.match(/^(?:[^省]+省)?([^市]+)市/)?.[1];
  if (!city || !userValue.startsWith(city)) return userValue;
  return userValue.slice(city.length).replace(/^的/, '') || userValue;
}

function decisionGeographyZoom(
  geography: Pick<DecisionGeography, 'geographic_scope'>,
) {
  if (geography.geographic_scope === 'REGION') return 6.5;
  if (geography.geographic_scope === 'LOCAL') return 12.5;
  return 10.5;
}

function isGroundedWorkReality(
  geography: DecisionGeography | null | undefined,
): geography is DecisionGeography & { lng: number; lat: number } {
  return isGroundedDecisionGeography(geography)
    && geography.identity_source === 'USER'
    && geography.intent_type === 'work_location';
}

export default function HomePage() {
  const searchParams = useSearchParams();
  const [conversationId, setConversationId] = useState(
    () => searchParams.get('conversation_id') ?? '',
  );
  const [profile, setProfile] = useState<LivingProfile | null>(null);
  const [properties, setProperties] = useState<Property[]>([]);
  const [projection, setProjection] = useState<GeographicProjection | null>(null);
  const [geographicGroundReady, setGeographicGroundReady] = useState(false);
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
  const [, setObservedWorkReality] = useState<
    DecisionGeography | null
  >(null);
  const [focusedChoiceIds, setFocusedChoiceIds] = useState<string[]>([]);
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);
  const [workPrecisionActionRequest, setWorkPrecisionActionRequest] = useState(0);
  const [rentAnswerPropertyId, setRentAnswerPropertyId] = useState<string | null>(null);
  const [rentFocusRequest, setRentFocusRequest] = useState(0);
  const [externalRentLookup, setExternalRentLookup] = useState<{
    propertyId: string;
    status: 'loading' | 'failed';
  } | null>(null);
  const [publicActionExecution, setPublicActionExecution] = useState<{
    propertyId: string;
    status: 'loading' | 'failed';
  } | null>(null);
  const latestSubmitIdRef = useRef(0);
  const lastFocusedCameraRef = useRef<{
    key: string;
    reorient: NonNullable<typeof reorient>;
  } | null>(null);
  const lastUserHomeGroceryFocusRef = useRef<string | null>(null);

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
      if (isGroundedDecisionGeography(decisionGeography)) {
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

  const handleGroundReadyChange = useCallback((ready: boolean) => {
    setGeographicGroundReady(ready);
  }, []);

  const handleCameraReady = useCallback(
    (nextReorient: (center: { lng: number; lat: number }, zoom: number) => void) => {
      setReorient(() => nextReorient);
    },
    [],
  );

  const clearChoiceFocus = useCallback(() => {
    setRentAnswerPropertyId(null);
    setFocusedChoiceIds([]);
    setPendingAction(null);
  }, []);

  const applyObservedDecisionGeography = useCallback((
    geography: DecisionGeography | null | undefined,
    submitId: number,
  ) => {
    if (
      latestSubmitIdRef.current !== submitId
      || !isGroundedDecisionGeography(geography)
    ) {
      return false;
    }

    const geographyChanged = shouldApplyObservedDecisionGeography({
      candidate: geography,
      baselineFingerprint: decisionGeographyFingerprint(restoredDecisionGeography),
      observationId: submitId,
      latestObservationId: latestSubmitIdRef.current,
    });
    if (geographyChanged) setRestoredDecisionGeography(geography);
    setDecisionWorldActive(true);
    if (isGroundedWorkReality(geography)) {
      setObservedWorkReality(geography);
    }
    if (geographyChanged) {
      reorient?.(
        { lng: geography.lng, lat: geography.lat },
        decisionGeographyZoom(geography),
      );
    }
    return true;
  }, [reorient, restoredDecisionGeography]);

  const focusChoice = useCallback((propertyId: string) => {
    setPendingAction((current) => current?.propertyId === propertyId ? current : null);
    setFocusedChoiceIds((current) => {
      if (current.includes(propertyId)) return current;
      if (current.length < 2) return [...current, propertyId];
      return [current[1], propertyId];
    });
  }, []);

  const togglePossibleLifeFocus = useCallback((propertyId: string) => {
    setRentAnswerPropertyId(null);
    setPendingAction(null);
    setFocusedChoiceIds((current) => (
      current.length === 1 && current[0] === propertyId ? [] : [propertyId]
    ));
  }, []);

  const handleExternalRent = useCallback(async (propertyId: string) => {
    if (!conversationId) return;
    setExternalRentLookup({ propertyId, status: 'loading' });
    setRentAnswerPropertyId(null);
    try {
      const result = await acquireExternalRent(conversationId, propertyId);
      if (result.status === 'UPDATED' && result.property) {
        const updatedProperty = result.property;
        setProperties(current => current.map(property => (
          property.id === updatedProperty.id ? updatedProperty : property
        )));
        setExternalRentLookup(null);
        return;
      }
      setExternalRentLookup({ propertyId, status: 'failed' });
      // Keep USER_PROVIDED Reality available through the existing one-shot Composer.
      setRentAnswerPropertyId(propertyId);
      setRentFocusRequest(current => current + 1);
    } catch {
      setExternalRentLookup({ propertyId, status: 'failed' });
      setRentAnswerPropertyId(propertyId);
      setRentFocusRequest(current => current + 1);
    }
  }, [conversationId]);

  const handlePublicRentAction = useCallback(async (propertyId: string) => {
    if (!conversationId) return;
    setPublicActionExecution({ propertyId, status: 'loading' });
    try {
      const result = await executePublicRentAction(conversationId, propertyId);
      if (result.status === 'EVIDENCE_READY') {
        setProperties(await getProperties(conversationId));
        setPublicActionExecution(null);
      } else if (result.status === 'NO_EVIDENCE') {
        setProperties(await getProperties(conversationId));
        setPublicActionExecution(null);
      } else {
        setPublicActionExecution({ propertyId, status: 'failed' });
      }
    } catch {
      setPublicActionExecution({ propertyId, status: 'failed' });
    }
  }, [conversationId]);

  const handleDailyGrocery = useCallback(async (propertyId: string): Promise<Property | null> => {
    if (!conversationId) return null;
    try {
      const result = await establishDailyGrocery(conversationId, propertyId);
      if (!result.property) return null;
      const updatedProperty = result.property;
      setProperties(current => current.map(property => (
        property.id === updatedProperty.id ? updatedProperty : property
      )));
      return updatedProperty;
    } catch (error: unknown) {
      console.error('Failed to establish Daily Grocery Reality:', error);
      return null;
    }
  }, [conversationId]);

  const handleLivingMeaning = useCallback(async (propertyId: string) => {
    if (!conversationId) return;
    try {
      const result = await formLivingMeaning(conversationId, propertyId);
      if (!result.property) return;
      const updatedProperty = result.property;
      setProperties(current => current.map(property => (
        property.id === updatedProperty.id ? updatedProperty : property
      )));
    } catch (error: unknown) {
      console.error('Failed to form Living Meaning:', error);
    }
  }, [conversationId]);

  const handlePlaceContext = useCallback(async (propertyId: string) => {
    if (!conversationId) return;
    try {
      const result = await establishPlaceContext(conversationId, propertyId);
      if (!result.property) return;
      const updatedProperty = result.property;
      setProperties(current => current.map(property => (
        property.id === updatedProperty.id ? updatedProperty : property
      )));
    } catch (error: unknown) {
      console.error('Failed to establish Place Context:', error);
    }
  }, [conversationId]);

  const enterPossibleLifeFocus = useCallback(async (home: Property) => {
    let reality = home;
    if (!reality.grocery_external_id) {
      const grounded = await handleDailyGrocery(home.id);
      if (grounded) reality = grounded;
    }
    await handleLivingMeaning(reality.id);
    await handlePlaceContext(reality.id);
  }, [handleDailyGrocery, handleLivingMeaning, handlePlaceContext]);

  const groundedWork = useMemo(() => {
    return profile?.geographic_status === 'GROUNDED'
      && typeof profile.lng === 'number'
      && typeof profile.lat === 'number'
      ? {
          lng: profile.lng,
          lat: profile.lat,
          identity: profile.geographic_identity ?? profile.work_location ?? '',
          displayIdentity: profile.work_location?.trim()
            ? profile.geographic_precision === 'AREA'
              ? formatAreaWorkIdentity(
                profile.work_location.trim(),
                profile.geographic_identity ?? '',
              )
              : profile.work_location.trim()
            : formatGeographicIdentity(
                profile.geographic_identity ?? '',
                profile.geographic_precision,
              ),
        }
      : null;
  }, [profile]);
  const workPrecisionUnknown = Boolean(
    groundedWork
    && profile?.geographic_precision === 'AREA'
    && typeof profile.commute_minutes === 'number',
  );

  useEffect(() => {
    if (!groundedWork || !geographicGroundReady) return;
    const frame = requestAnimationFrame(() => setWorkVisible(true));
    return () => cancelAnimationFrame(frame);
  }, [geographicGroundReady, groundedWork]);
  const groundedChoices = useMemo(
    () => [
      ...properties.filter(
        (property): property is Property & { lng: number; lat: number } =>
          property.conversation_id === conversationId
          && property.provenance === 'USER_PROVIDED'
          && property.geographic_status === 'GROUNDED'
          && Boolean(property.title?.trim())
          && typeof property.lng === 'number' && Number.isFinite(property.lng)
          && typeof property.lat === 'number' && Number.isFinite(property.lat),
      ),
      ...properties.filter(
        (property): property is Property & { lng: number; lat: number } =>
          property.geographic_status === 'GROUNDED'
          && property.conversation_id === conversationId
          && property.provenance === 'AMAP_RESIDENTIAL_POI'
          && Boolean(property.external_id && property.title?.trim())
          && typeof property.commute_minutes === 'number'
          && Number.isFinite(property.commute_minutes)
          && property.commute_minutes > 0
          && (property.commute_mode === 'WALKING' || property.commute_mode === 'PUBLIC_TRANSIT')
          && typeof property.lng === 'number'
          && Number.isFinite(property.lng) && Math.abs(property.lng) <= 180
          && typeof property.lat === 'number'
          && Number.isFinite(property.lat) && Math.abs(property.lat) <= 90,
      ).slice(
        0,
        groundedWork && profile?.geographic_precision === 'PLACE' ? 1 : 0,
      ),
    ],
    [conversationId, groundedWork, profile?.geographic_precision, properties],
  );
  const standaloneWorkReality = true;
  const housingFitLocations = useMemo(
    () => groundedWork && groundedChoices.some(
      (property) => property.provenance === 'AMAP_RESIDENTIAL_POI',
    )
      ? [
          { lng: groundedWork.lng, lat: groundedWork.lat },
          ...groundedChoices.filter(
            (property) => property.provenance === 'AMAP_RESIDENTIAL_POI',
          ).map((property) => ({
            lng: property.lng,
            lat: property.lat,
          })),
        ]
      : [],
    [groundedChoices, groundedWork],
  );
  const focusedChoices = useMemo(
    () => focusedChoiceIds
      .map((propertyId) => groundedChoices.find(({ id }) => id === propertyId))
      .filter((property): property is Property & { lng: number; lat: number } => Boolean(property)),
    [focusedChoiceIds, groundedChoices],
  );
  const singleFocusedHome = focusedChoices.length === 1 ? focusedChoices[0] : null;
  useEffect(() => {
    if (
      !geographicGroundReady
      || !singleFocusedHome
      || singleFocusedHome.provenance !== 'USER_PROVIDED'
    ) {
      lastUserHomeGroceryFocusRef.current = null;
      return;
    }
    const focusKey = `${conversationId}:${singleFocusedHome.id}`;
    if (lastUserHomeGroceryFocusRef.current === focusKey) return;
    lastUserHomeGroceryFocusRef.current = focusKey;
    void enterPossibleLifeFocus(singleFocusedHome);
  }, [conversationId, enterPossibleLifeFocus, geographicGroundReady, singleFocusedHome]);
  const focusedHomeCamera = focusedHomeViewport(singleFocusedHome);
  const focusedHomeCameraKey = singleFocusedHome && focusedHomeCamera
    ? `${singleFocusedHome.id}:${singleFocusedHome.lng}:${singleFocusedHome.lat}`
    : null;
  const dualFocusActive = focusedChoices.length === 2;
  const worldFitLocations = useMemo(
    () => groundedWork && dualFocusActive
      ? [
          { lng: groundedWork.lng, lat: groundedWork.lat },
          ...focusedChoices.map(({ lng, lat }) => ({ lng, lat })),
        ]
      : housingFitLocations,
    [dualFocusActive, focusedChoices, groundedWork, housingFitLocations],
  );
  const dualFocusFitKey = dualFocusActive
    ? focusedChoices.map(({ id }) => id).join('|')
    : undefined;
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
      decisionGeographyZoom(restoredDecisionGeography),
    );
  }, [
    conversationId,
    hasHousingDecisionExtent,
    reorient,
    restoredDecisionGeography,
  ]);

  useEffect(() => {
    if (!reorient || !focusedHomeCamera || !focusedHomeCameraKey) {
      lastFocusedCameraRef.current = null;
      return;
    }
    if (
      lastFocusedCameraRef.current?.key === focusedHomeCameraKey
      && lastFocusedCameraRef.current.reorient === reorient
    ) return;
    lastFocusedCameraRef.current = { key: focusedHomeCameraKey, reorient };
    reorient(focusedHomeCamera.center, focusedHomeCamera.zoom);
  }, [
    focusedHomeCamera,
    focusedHomeCameraKey,
    reorient,
  ]);

  const handleSubmit = useCallback(async (message: string) => {
    const currentConversationId = conversationId || createClientId();
    const focusedUserReality = focusedChoiceIds.length === 1
      ? groundedChoices.find((choice) => choice.id === focusedChoiceIds[0])
      : undefined;
    const submitId = latestSubmitIdRef.current + 1;
    latestSubmitIdRef.current = submitId;
    let consequenceRevision = 0;
    let pendingFocusPropertyId: string | undefined;

    setPhase('forming');
    setWorkVisible(false);
    setObservedWorkReality(null);
    try {
      let markWorldStateReady: (() => void) | undefined;
      const worldStateReady = new Promise<void>((resolve) => {
        markWorldStateReady = resolve;
      });
      const reconcileWorldConsequences = async () => {
        const revision = ++consequenceRevision;
        const [durableProfile, durableProperties] = await Promise.all([
          getLivingProfile(currentConversationId),
          getProperties(currentConversationId),
        ]);
        if (latestSubmitIdRef.current !== submitId || revision !== consequenceRevision) return;
        setProfile(durableProfile);
        setProperties(durableProperties);
        if (pendingFocusPropertyId && durableProperties.some((property) =>
          property.id === pendingFocusPropertyId
          && property.conversation_id === currentConversationId
          && property.provenance === 'USER_PROVIDED'
          && property.geographic_status === 'GROUNDED'
          && typeof property.lng === 'number'
          && typeof property.lat === 'number',
        )) {
          setFocusedChoiceIds([pendingFocusPropertyId]);
        }
        setPhase(
          durableProfile?.geographic_status === 'GROUNDED' ? 'formed' : 'empty',
        );
        if (durableProfile?.geographic_status === 'GROUNDED') {
          setObservedWorkReality(null);
          requestAnimationFrame(() => setWorkVisible(true));
        }
      };
      const chatCompletion = streamMessage({
        conversationId: currentConversationId,
        message,
        rentPropertyId: focusedChoiceIds.length === 1
          && focusedChoiceIds[0] === rentAnswerPropertyId
          ? rentAnswerPropertyId : undefined,
        userRealityPropertyId: focusedUserReality?.id,
        userDecisionPropertyId: focusedUserReality?.decision_readiness === 'DECISION_READY'
          && !focusedUserReality.user_decision_expression
          ? focusedUserReality.id : undefined,
        clarificationTarget: workPrecisionUnknown && workPrecisionActionRequest > 0
          ? 'WORK_LOCATION' : undefined,
        currentGeographicReality: currentLocation,
        onChunk: () => {},
        onWorldStateReady: () => markWorldStateReady?.(),
        onWorldConsequenceReady: (focusPropertyId) => {
          if (focusPropertyId) pendingFocusPropertyId = focusPropertyId;
          void reconcileWorldConsequences().catch((error: unknown) => {
            console.error('Failed to reconcile persisted World consequence:', error);
          });
        },
      });
      // The selected clarification belongs to this answer, not subsequent turns.
      setWorkPrecisionActionRequest(0);
      setRentAnswerPropertyId(null);

      // The stream establishes the conversation and owner cookie before reads.
      // Missing geography is valid (200 null); do not poll an unowned cold start.
      await Promise.race([
        worldStateReady,
        chatCompletion.then(() => undefined),
      ]);
      const earlyRevision = consequenceRevision;
      const [nextProfile, nextProperties, decisionGeography] = await Promise.all([
        getLivingProfile(currentConversationId),
        getProperties(currentConversationId),
        getDecisionGeography(currentConversationId),
      ]);
      if (!conversationId) {
        setConversationId(currentConversationId);
        window.history.replaceState(
          window.history.state,
          '',
          '/?conversation_id=' + encodeURIComponent(currentConversationId),
        );
      }
      if (latestSubmitIdRef.current !== submitId) return;
      if (earlyRevision === consequenceRevision) {
        if (nextProfile) setProfile(nextProfile);
        setProperties(nextProperties);
        setPendingAction((current) => {
          if (!current) return null;
          const target = nextProperties.find(({ id }) => id === current.propertyId);
          return target && typeof target.rent === 'number' ? null : current;
        });
        setPhase(nextProfile?.geographic_status === 'GROUNDED' ? 'formed' : 'empty');
        if (nextProfile?.geographic_status === 'GROUNDED') {
          requestAnimationFrame(() => setWorkVisible(true));
        }
      }
      if (isGroundedDecisionGeography(decisionGeography)) {
        applyObservedDecisionGeography(decisionGeography, submitId);
      } else if (
        !isGroundedDecisionGeography(restoredDecisionGeography)
        && currentLocation
      ) {
        reorient?.(currentLocation, 12.5);
      }
      await chatCompletion;
      const [completedProfile, completedProperties] = await Promise.all([
        getLivingProfile(currentConversationId),
        getProperties(currentConversationId),
      ]);
      if (latestSubmitIdRef.current !== submitId) return;
      if (completedProfile) {
        setProfile(completedProfile);
        if (completedProfile.geographic_status === 'GROUNDED') {
          setObservedWorkReality(null);
        }
        setPhase(completedProfile.geographic_status === 'GROUNDED' ? 'formed' : 'empty');
        if (completedProfile.geographic_status === 'GROUNDED') {
          requestAnimationFrame(() => setWorkVisible(true));
        }
      }
      setProperties(completedProperties);
      setPendingAction((current) => {
        if (!current) return null;
        const target = completedProperties.find(({ id }) => id === current.propertyId);
        return target && typeof target.rent === 'number' ? null : current;
      });
    } catch (error: unknown) {
      console.error('Failed to form First Reality:', error);
      if (latestSubmitIdRef.current === submitId) {
        try {
          const [persistedProfile, persistedProperties] = await Promise.all([
            getLivingProfile(currentConversationId),
            getProperties(currentConversationId),
          ]);
          if (latestSubmitIdRef.current !== submitId) return;
          setProfile(persistedProfile);
          setProperties(persistedProperties);
          setPhase(
            persistedProfile?.geographic_status === 'GROUNDED'
              ? 'formed'
              : 'empty',
          );
          if (persistedProfile?.geographic_status === 'GROUNDED') {
            requestAnimationFrame(() => setWorkVisible(true));
          }
        } catch (restoreError: unknown) {
          console.error('Failed to restore persisted World State:', restoreError);
          setPhase('empty');
        }
      }
    }
  }, [
    applyObservedDecisionGeography,
    conversationId,
    currentLocation,
    reorient,
    restoredDecisionGeography,
    workPrecisionUnknown,
    workPrecisionActionRequest,
    rentAnswerPropertyId,
    focusedChoiceIds,
    groundedChoices,
  ]);

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
  const tradeoffMeaning = useMemo(() => {
    if (!dualFocusActive) return null;
    const [first, second] = focusedChoices;
    if (
      typeof first.commute_minutes !== 'number'
      || typeof second.commute_minutes !== 'number'
    ) {
      return null;
    }
    const difference = Math.abs(first.commute_minutes - second.commute_minutes);
    if (difference === 0) return '通勤时间相同';
    const faster = first.commute_minutes < second.commute_minutes ? first : second;
    const slower = faster.id === first.id ? second : first;
    return `${faster.title ?? '一个选择'} 比 ${slower.title ?? '另一个选择'} 少 ${difference} min 通勤`;
  }, [dualFocusActive, focusedChoices]);
  const tradeoffPosition = useMemo(() => {
    if (!dualFocusActive) return null;
    const positions = focusedChoices.map(({ id }) => choicePositions[id]);
    if (positions.some((position) => !position)) return null;
    return {
      x: (positions[0].x + positions[1].x) / 2,
      y: (positions[0].y + positions[1].y) / 2 + 88,
    };
  }, [choicePositions, dualFocusActive, focusedChoices]);
  const restoredDecisionCenter = useMemo(
    () => restoredDecisionGeography?.conversation_id === conversationId
      && isGroundedDecisionGeography(restoredDecisionGeography)
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
          fitLocations={worldFitLocations}
          fitRequestKey={dualFocusFitKey}
          initialCenter={initialMapCenter}
          initialZoom={
            restoredDecisionCenter && restoredDecisionGeography
              ? decisionGeographyZoom(restoredDecisionGeography)
              : 12.5
          }
          onProjectionReady={handleProjectionReady}
          onGroundReadyChange={handleGroundReadyChange}
          onCameraReady={handleCameraReady}
          onMapClick={clearChoiceFocus}
        />
      )}
      <section
        aria-label="Living World"
        className={`relative z-10 min-h-screen ${decisionWorldActive ? 'pointer-events-none' : ''}`}
      >
        {geographicGroundReady && workVisible && workPosition && groundedChoices.map((home) => {
          if (home.provenance !== 'AMAP_RESIDENTIAL_POI') return null;
          const position = choicePositions[home.id];
          if (!position) return null;
          const focused = focusedChoiceIds.includes(home.id);
          const meaning = `${home.commute_minutes}min · ${home.commute_mode === 'WALKING' ? '步行' : '公共交通'}`;
          const groceryPosition = projection
            && typeof home.grocery_lng === 'number'
            && typeof home.grocery_lat === 'number'
            && typeof home.grocery_walking_minutes === 'number'
            ? {
                ...projection({ lng: home.grocery_lng, lat: home.grocery_lat }),
                walkingMinutes: home.grocery_walking_minutes,
              }
            : undefined;
          return (
            <PossibleLifeProjection
              key={home.id}
              work={{ ...workPosition, name: groundedWork?.displayIdentity ?? '' }}
              home={{ ...position, name: home.title ?? '' }}
              grocery={groceryPosition}
              meaning={meaning}
              livingMeaning={home.living_meaning}
              currentJudgment={home.current_judgment}
              decisionReadiness={home.decision_readiness}
              userDecisionExpression={home.user_decision_source === 'USER_PROVIDED'
                ? home.user_decision_expression : null}
              independentKitchen={home.independent_kitchen_source === 'USER_PROVIDED'
                ? home.independent_kitchen : null}
              indoorSoundObservation={home.indoor_sound_observation_source === 'USER_PROVIDED'
                ? home.indoor_sound_observation : null}
              meaningfulUnknown={home.meaningful_unknown}
              meaningfulUnknownWhy={home.meaningful_unknown_why}
              realityActionLabel={home.reality_action_label}
              realityActionWhy={home.reality_action_why}
              realityActionType={home.reality_action_type}
              publicRentEvidence={home.public_rent_evidence}
              publicActionOutcome={home.public_action_outcome}
              feedbackMoveLabel={home.feedback_move_label}
              feedbackMoveWhy={home.feedback_move_why}
              actionExecutionStatus={publicActionExecution?.propertyId === home.id
                ? publicActionExecution.status : 'idle'}
              onExecutePublicAction={() => { void handlePublicRentAction(home.id); }}
              focused={focused}
              rent={home.rent_source === 'USER_PROVIDED' || home.rent_source === 'USER_CONFIRMED_REALITY' || home.rent_source === 'EXTERNAL_SOURCE'
                ? home.rent : null}
              budget={profile?.budget ?? null}
              rentSourceAvailable={home.rent_source === 'EXTERNAL_SOURCE' && Boolean(home.rent_source_reference)}
              rentLookupStatus={externalRentLookup?.propertyId === home.id
                ? externalRentLookup.status : 'idle'}
              onAskRent={() => {
                setWorkPrecisionActionRequest(0);
                void handleExternalRent(home.id);
              }}
              onToggle={() => {
                togglePossibleLifeFocus(home.id);
                if (!focused) {
                  void enterPossibleLifeFocus(home);
                }
              }}
            />
          );
        })}
        {geographicGroundReady && groundedWork && workPosition && groundedChoices.length === 0 && (
          <div
            className={
              'absolute -translate-x-1/2 -translate-y-1/2 text-center transition-opacity delay-300 duration-700 ease-out motion-reduce:delay-0 motion-reduce:transition-none ' +
              (workVisible ? 'opacity-100' : 'opacity-0')
            }
            style={{ left: workPosition.x, top: workPosition.y }}
          >
            <div
              className={`world-object work-anchor ${focusedChoiceIds.length > 0 ? 'world-object-context' : ''}`}
              aria-label={standaloneWorkReality
                ? `${groundedWork.displayIdentity}，${workPrecisionUnknown ? '工作区域' : '工作'}`
                : [
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
              {!workPrecisionUnknown && (
                <span className="object-mark">{standaloneWorkReality ? '●' : '◎'}</span>
              )}
              {!standaloneWorkReality && (
                <span className="object-kicker mt-2">我的工作</span>
              )}
              <span className="object-name mt-2">
                {groundedWork.displayIdentity}
              </span>
              {standaloneWorkReality ? (
                <>
                  <span className="object-kicker mt-1">
                    {workPrecisionUnknown ? '工作区域' : '工作'}
                  </span>
                  {workPrecisionUnknown && (
                    <button
                      type="button"
                      className="pointer-events-auto mt-3 border-0 bg-transparent p-0 font-mono text-[11px] font-medium tracking-[0.08em] text-slate-700 underline decoration-slate-400/70 underline-offset-4 transition-colors hover:text-slate-950"
                      onClick={(event) => {
                        event.stopPropagation();
                        setWorkPrecisionActionRequest((current) => current + 1);
                      }}
                    >
                      具体工作地点？
                    </button>
                  )}
                </>
              ) : (
                <>
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
                </>
              )}
            </div>
          </div>
        )}

        {geographicGroundReady && groundedChoices.map((property) => {
          if (property.provenance === 'AMAP_RESIDENTIAL_POI') return null;
          const position = choicePositions[property.id];
          if (!position) return null;
          const focused = focusedChoiceIds.includes(property.id);
          const focusedOrder = focusedChoiceIds.indexOf(property.id);
          const singleFocused = focused && !dualFocusActive;
          const groundedGrocery = singleFocused
            && Boolean(property.grocery_external_id && property.grocery_name)
            && typeof property.grocery_lng === 'number'
            && Number.isFinite(property.grocery_lng)
            && typeof property.grocery_lat === 'number'
            && Number.isFinite(property.grocery_lat)
            && typeof property.grocery_walking_minutes === 'number'
            && property.grocery_walking_minutes > 0;
          const placeContext = singleFocused ? (property.place_context ?? []).filter(item => (
            Boolean(item.external_id && item.name && item.identity)
            && Number.isFinite(item.lng) && Number.isFinite(item.lat)
            && ['COMMERCIAL', 'TRANSIT', 'EDUCATION'].includes(item.category)
          )) : [];
          const rentActionPending = pendingAction?.propertyId === property.id
            && pendingAction.type === 'CONFIRM_RENT'
            && pendingAction.status === 'PENDING';
          const receded = focusedChoiceIds.length > 0 && !focused;
          const budgetMeaning = deriveBudgetMeaning(profile?.budget, property);
          const confirmedWithinBudget = budgetMeaning === '预算内';
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
                className={`world-object choice-object pointer-events-auto appearance-none border-0 bg-transparent p-0 text-center focus:outline-none ${focused ? 'choice-object-focused' : ''} ${confirmedWithinBudget ? 'choice-object-confirmed-viable' : ''} ${receded ? 'world-object-receded' : ''}`}
                aria-label={[
                  `聚焦 ${property.title ?? '未命名选择'}`,
                  budgetMeaning,
                ].filter(Boolean).join('，')}
                aria-pressed={focused}
                onClick={(event) => {
                  event.stopPropagation();
                  focusChoice(property.id);
                }}
              >
                <span className="object-mark">
                  {focused ? '◉' : dualFocusActive ? '○' : '●'}
                </span>
                {focused ? (
                  <span
                    className={`choice-focus-copy ${dualFocusActive ? (focusedOrder === 0 ? 'choice-focus-copy-left' : 'choice-focus-copy-right') : 'choice-focus-copy-single'}`}
                  >
                    <span className="object-kicker">可能的家</span>
                    <span className="object-name mt-2">
                      {property.title ?? '未命名选择'}
                    </span>
                    {typeof property.commute_minutes === 'number' && (
                      <span className="mt-1 font-mono text-[10px] font-medium tracking-[0.08em] text-slate-700">
                        到工作地点 {property.commute_minutes} min
                        {commuteMode ? ` · ${commuteMode}` : ''}
                      </span>
                    )}
                    {singleFocused && property.rent === null && (
                      <span className="choice-unknown mt-2">
                        <span>租金 ?</span>
                        <span>仍需确认</span>
                      </span>
                    )}
                    {singleFocused && typeof property.rent === 'number' && (
                      <span className="choice-confirmed-reality mt-2">
                        <span className="choice-confirmed-rent">
                          ¥{property.rent} / 月
                        </span>
                        {budgetMeaning && (
                          <span className={`choice-budget-meaning ${budgetMeaning === '超预算' ? 'choice-budget-meaning-over' : ''}`}>
                            {budgetMeaning}
                          </span>
                        )}
                      </span>
                    )}
                    {groundedGrocery && (
                      <span className="mt-2 max-w-56 whitespace-normal text-left text-xs text-emerald-900">
                        <span className="block font-medium">日常采购</span>
                        <span className="mt-1 block">{property.grocery_name}</span>
                        <span className="mt-1 block">步行 {property.grocery_walking_minutes} min</span>
                      </span>
                    )}
                    {placeContext.map(item => (
                      <span key={item.category} className="mt-2 block max-w-56 whitespace-normal text-left text-xs text-slate-700">
                        <span className="font-medium">{{ COMMERCIAL: '商业', TRANSIT: '出行', EDUCATION: '教育' }[item.category]} · {item.name}</span>
                        {typeof item.walking_minutes === 'number' && item.walking_minutes > 0 && (
                          <span className="mt-1 block">步行 {item.walking_minutes} min</span>
                        )}
                      </span>
                    ))}
                    {singleFocused && property.living_meaning && (
                      <span className="mt-3 max-w-56 whitespace-normal text-left text-xs leading-relaxed text-slate-600">
                        {property.living_meaning}
                      </span>
                    )}
                    {singleFocused && property.current_judgment && (
                      <span className="mt-2 max-w-56 whitespace-normal border-l border-slate-400/60 pl-2 text-left text-xs font-medium leading-relaxed text-slate-800">
                        {property.current_judgment}
                      </span>
                    )}
                    {singleFocused && property.decision_readiness === 'DECISION_READY' && !property.user_decision_expression && (
                      <span className="mt-2 max-w-56 whitespace-normal text-left text-xs text-slate-600">
                        现在已经可以判断这个选择了
                      </span>
                    )}
                    {singleFocused && property.meaningful_unknown && (
                      <span className="mt-3 max-w-56 whitespace-normal text-left text-xs leading-relaxed text-slate-600">
                        <span className="block text-[10px] tracking-[0.08em] text-slate-400">还需要弄清楚</span>
                        <span className="mt-1 block">{property.meaningful_unknown}</span>
                        {property.meaningful_unknown_why && (
                          <span className="mt-1 block text-[11px] text-slate-500">{property.meaningful_unknown_why}</span>
                        )}
                      </span>
                    )}
                    {singleFocused && property.meaningful_unknown && property.reality_action_label && (
                      <span className="mt-3 max-w-56 whitespace-normal text-left text-xs leading-relaxed text-slate-600">
                        <span className="block text-[10px] tracking-[0.08em] text-slate-400">下一步</span>
                        <span className="mt-1 block">{property.reality_action_label}</span>
                        {property.reality_action_why && (
                          <span className="mt-1 block text-[11px] text-slate-500">{property.reality_action_why}</span>
                        )}
                      </span>
                    )}
                  </span>
                ) : (
                  <>
                    <span className="object-name mt-2">
                      {property.title ?? '未命名选择'}
                    </span>
                    {typeof property.commute_minutes === 'number' && (
                      <span className="mt-1 font-mono text-[10px] font-medium tracking-[0.08em] text-slate-700">
                        {property.commute_minutes} min
                      </span>
                    )}
                  </>
                )}
              </button>
              {singleFocused && property.rent === null && (
                <button
                  type="button"
                  className={`choice-reality-action pointer-events-auto ${rentActionPending ? 'choice-reality-action-pending' : ''}`}
                  aria-label={rentActionPending ? '待确认租金' : '确认租金'}
                  aria-pressed={rentActionPending}
                  onClick={(event) => {
                    event.stopPropagation();
                    setPendingAction({
                      propertyId: property.id,
                      type: 'CONFIRM_RENT',
                      status: 'PENDING',
                    });
                  }}
                >
                  {rentActionPending ? '→ 确认租金' : '确认租金 →'}
                </button>
              )}
            </div>
          );
        })}

        {geographicGroundReady && tradeoffMeaning && tradeoffPosition && (
          <div
            className="compare-meaning pointer-events-none absolute z-30 -translate-x-1/2 -translate-y-1/2 text-center"
            style={{ left: tradeoffPosition.x, top: tradeoffPosition.y }}
            aria-label={`比较结果：${tradeoffMeaning}`}
          >
            <div className="font-mono text-[11px] font-medium tracking-[0.18em] text-slate-600">
              {(focusedChoices[0].title ?? 'Choice A')} ↔ {(focusedChoices[1].title ?? 'Choice B')}
            </div>
            <div className="mt-2 text-[16px] font-semibold tracking-[0.02em] text-slate-900">
              {tradeoffMeaning}
            </div>
          </div>
        )}
      </section>
      <div className="absolute inset-x-0 bottom-0 z-20 px-5 pb-5 sm:px-10 sm:pb-8">
        <div className="mx-auto max-w-3xl">
          <ConversationComposer
            disabled={phase === 'forming'}
            variant="ambient"
            placeholder={rentAnswerPropertyId && focusedChoiceIds.includes(rentAnswerPropertyId)
              ? '这套房实际租金是多少？'
              : workPrecisionUnknown && workPrecisionActionRequest > 0
              ? `你在${groundedWork?.displayIdentity ?? '这个区域'}具体哪里工作？`
              : '告诉 LiveOS，你现在最想解决的生活问题……'}
            focusRequestKey={workPrecisionActionRequest + rentFocusRequest}
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
