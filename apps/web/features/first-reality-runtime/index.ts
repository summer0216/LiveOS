'use client';

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type Dispatch,
  type RefObject,
  type SetStateAction,
} from 'react';

import type { FirstOpenRuntimeStage } from '@/features/first-open';
import type { GeographicCameraTarget } from '@/features/living-map/AMapGround';
import { createClientId } from '@/lib/createClientId';
import {
  decisionGeographyZoom,
  geographicScaleZoom,
  realityLevelForPrecision,
} from '@/lib/geographicScaleContract';
import {
  decisionGeographyFingerprint,
  isGroundedDecisionGeography,
  shouldApplyObservedDecisionGeography,
} from '@/lib/decisionGeographyState';
import type { PossibleLifeFocus, WorkSubjectFocus } from '@/lib/worldConsequence';
import { streamMessage } from '@/services/chat';
import {
  getDecisionGeography,
  type DecisionGeography,
} from '@/services/decisionGeography';
import { getPossibleLives, type PossibleLifeWorldState } from '@/services/possibleLife';
import { getLivingProfile, type LivingProfile } from '@/services/profile';
import { getProperties, type Property } from '@/services/property';

export type FirstRealityPhase =
  | 'empty'
  | 'forming'
  | 'grounding'
  | 'revealing'
  | 'formed';

export interface AuthoritativeGroundedReality {
  center: { lng: number; lat: number };
  identity: string;
  focusZoom: number;
  worldZoom: number;
}

export type FirstRealityCameraReorient = (
  center: { lng: number; lat: number },
  target: GeographicCameraTarget,
  occlusion?: HTMLElement | null,
  screenAnchor?: HTMLElement | null,
) => void;

interface FirstRealityRuntimeOptions {
  initialConversationId: string;
  onWorldConsequenceReady?: (
    focusPropertyId?: string,
    focusSubject?: WorkSubjectFocus,
    focusPossibleLife?: PossibleLifeFocus,
  ) => void;
  onPersistedRealityReconciled?: (
    conversationId: string,
    properties: readonly Property[],
  ) => void;
}

interface FirstRealityRuntime {
  conversationId: string;
  profile: LivingProfile | null;
  properties: Property[];
  possibleLives: PossibleLifeWorldState[];
  setProperties: Dispatch<SetStateAction<Property[]>>;
  restoredDecisionGeography: DecisionGeography | null | undefined;
  decisionWorldActive: boolean;
  phase: FirstRealityPhase;
  submittedExpression: string | null;
  authoritativeReality: AuthoritativeGroundedReality | null;
  firstRealityTransition: AuthoritativeGroundedReality | null;
  currentLocation: { lng: number; lat: number } | null;
  hasGroundedWorld: boolean;
  firstOpenActive: boolean;
  firstOpenStage: FirstOpenRuntimeStage;
  worldVisible: boolean;
  geographicGroundReady: boolean;
  reorient: FirstRealityCameraReorient | null;
  placeAnchorRef: RefObject<HTMLSpanElement | null>;
  submit: (expression: string) => Promise<void>;
  onGroundReadyChange: (ready: boolean) => void;
  onCameraReady: (reorient: FirstRealityCameraReorient) => void;
  onGroundingSettled: () => void;
  onWorldSettled: () => void;
}

export function resolveAuthoritativeGroundedReality(
  profile: LivingProfile | null,
  properties: readonly Property[],
  decisionGeography?: DecisionGeography | null,
  expression?: string,
): AuthoritativeGroundedReality | null {
  const normalizedExpression = expression?.normalize('NFKC').replace(/\s+/g, '');
  const groundedHomes = properties.filter((property) => (
    property.provenance === 'USER_PROVIDED'
    && property.geographic_status === 'GROUNDED'
    && Boolean(property.title?.trim())
    && typeof property.lng === 'number'
    && Number.isFinite(property.lng)
    && typeof property.lat === 'number'
    && Number.isFinite(property.lat)
  ));
  const home = normalizedExpression
    ? groundedHomes.find((property) => (
        property.title
        && normalizedExpression.includes(
          property.title.trim().normalize('NFKC').replace(/\s+/g, ''),
        )
      ))
    : groundedHomes[0];
  if (home?.title && home.geographic_precision) {
    return {
      center: { lng: home.lng as number, lat: home.lat as number },
      identity: home.title.trim(),
      focusZoom: geographicScaleZoom(
        realityLevelForPrecision(home.geographic_precision),
        'FOCUS',
      ),
      worldZoom: geographicScaleZoom(
        realityLevelForPrecision(home.geographic_precision),
        'SEE',
      ),
    };
  }

  if (
    decisionGeography
    && isGroundedDecisionGeography(decisionGeography)
    && (
      !normalizedExpression
      || (
        decisionGeography.identity_source === 'USER'
        && normalizedExpression.includes(
          decisionGeography.identity.normalize('NFKC').replace(/\s+/g, ''),
        )
      )
    )
  ) {
    return {
      center: { lng: decisionGeography.lng, lat: decisionGeography.lat },
      identity: decisionGeography.identity,
      focusZoom: decisionGeographyZoom(decisionGeography, 'FOCUS'),
      worldZoom: decisionGeographyZoom(decisionGeography, 'SEE'),
    };
  }

  if (
    profile?.geographic_status === 'GROUNDED'
    && typeof profile.lng === 'number'
    && typeof profile.lat === 'number'
    && profile.geographic_precision
  ) {
    const identities = [profile.work_location, profile.geographic_identity]
      .map((value) => value?.trim())
      .filter((value): value is string => Boolean(value));
    const identity = normalizedExpression
      ? identities.find((value) => normalizedExpression.includes(
          value.normalize('NFKC').replace(/\s+/g, ''),
        ))
      : identities[0];
    if (!identity) return null;
    return {
      center: { lng: profile.lng, lat: profile.lat },
      identity,
      focusZoom: geographicScaleZoom(
        realityLevelForPrecision(profile.geographic_precision),
        'FOCUS',
      ),
      worldZoom: geographicScaleZoom(
        realityLevelForPrecision(profile.geographic_precision),
        'SEE',
      ),
    };
  }

  return null;
}

function hasAdmittedPossibleLifeReality(
  conversationId: string,
  properties: readonly Property[],
  possibleLives: readonly PossibleLifeWorldState[],
) {
  const residenceIds = new Set(
    possibleLives.map((possibleLife) => possibleLife.residence_property_id),
  );
  return properties.some((property) => (
    property.conversation_id === conversationId
    && property.provenance === 'AMAP_RESIDENTIAL_POI'
    && property.geographic_status === 'GROUNDED'
    && residenceIds.has(property.id)
    && Boolean(property.external_id && property.title?.trim())
    && typeof property.commute_minutes === 'number'
    && Number.isFinite(property.commute_minutes)
    && property.commute_minutes > 0
    && (property.commute_mode === 'WALKING' || property.commute_mode === 'PUBLIC_TRANSIT')
    && typeof property.lng === 'number'
    && Number.isFinite(property.lng)
    && Math.abs(property.lng) <= 180
    && typeof property.lat === 'number'
    && Number.isFinite(property.lat)
    && Math.abs(property.lat) <= 90
  ));
}

export default function useFirstRealityRuntime({
  initialConversationId,
  onWorldConsequenceReady,
  onPersistedRealityReconciled,
}: FirstRealityRuntimeOptions): FirstRealityRuntime {
  const [conversationId, setConversationId] = useState(initialConversationId);
  const [profile, setProfile] = useState<LivingProfile | null>(null);
  const [properties, setProperties] = useState<Property[]>([]);
  const [possibleLives, setPossibleLives] = useState<PossibleLifeWorldState[]>([]);
  const [restoredDecisionGeography, setRestoredDecisionGeography] = useState<
    DecisionGeography | null | undefined
  >(undefined);
  const [phase, setPhase] = useState<FirstRealityPhase>('empty');
  const [submittedExpression, setSubmittedExpression] = useState<string | null>(null);
  const [firstRealityTransition, setFirstRealityTransition] = useState<
    AuthoritativeGroundedReality | null
  >(null);
  const [groundingSettled, setGroundingSettled] = useState(false);
  const [currentLocation, setCurrentLocation] = useState<{
    lng: number;
    lat: number;
  } | null>(null);
  const [geographicGroundReady, setGeographicGroundReady] = useState(false);
  const [reorient, setReorient] = useState<FirstRealityCameraReorient | null>(null);
  const placeAnchorRef = useRef<HTMLSpanElement>(null);
  const latestSubmitIdRef = useRef(0);
  const skipRestoreConversationRef = useRef<string | null>(null);
  const decisionGeographyRef = useRef<DecisionGeography | null | undefined>(undefined);
  const onWorldConsequenceReadyRef = useRef(onWorldConsequenceReady);
  const onPersistedRealityReconciledRef = useRef(onPersistedRealityReconciled);

  useEffect(() => {
    decisionGeographyRef.current = restoredDecisionGeography;
  }, [restoredDecisionGeography]);

  useEffect(() => {
    onWorldConsequenceReadyRef.current = onWorldConsequenceReady;
  }, [onWorldConsequenceReady]);

  useEffect(() => {
    onPersistedRealityReconciledRef.current = onPersistedRealityReconciled;
  }, [onPersistedRealityReconciled]);

  useEffect(() => {
    let settled = false;
    const markLocationUnknown = () => {
      if (settled) return;
      settled = true;
      console.info('[First Open] Current Geographic Reality unavailable; remaining unknown');
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
    if (skipRestoreConversationRef.current === conversationId) {
      skipRestoreConversationRef.current = null;
      return;
    }

    let active = true;
    void Promise.all([
      getLivingProfile(conversationId),
      getProperties(conversationId),
      getDecisionGeography(conversationId),
      getPossibleLives(conversationId),
    ]).then(([nextProfile, nextProperties, decisionGeography, nextPossibleLives]) => {
      if (!active) return;
      const restoredReality = resolveAuthoritativeGroundedReality(
        nextProfile,
        nextProperties,
        decisionGeography,
      );
      setProfile(nextProfile);
      setProperties(nextProperties);
      setPossibleLives(nextPossibleLives);
      decisionGeographyRef.current = decisionGeography;
      setRestoredDecisionGeography(decisionGeography);
      setPhase(restoredReality ? 'formed' : 'empty');
    }).catch((error: unknown) => {
      console.error('Failed to restore First Reality:', error);
    });

    return () => {
      active = false;
    };
  }, [conversationId]);

  const submit = useCallback(async (expression: string) => {
    const message = expression.trim();
    if (!message) return;

    const currentConversationId = conversationId || createClientId();
    const submitId = latestSubmitIdRef.current + 1;
    latestSubmitIdRef.current = submitId;
    let consequenceRevision = 0;
    let firstRealityRevealStarted = false;

    setSubmittedExpression(message);
    setFirstRealityTransition(null);
    setGroundingSettled(false);
    setPhase('forming');

    const applySceneResolution = (
      nextProfile: LivingProfile | null,
      nextProperties: readonly Property[],
      nextDecisionGeography?: DecisionGeography | null,
      settleIfMissing = false,
    ) => {
      const transition = resolveAuthoritativeGroundedReality(
        nextProfile,
        nextProperties,
        nextDecisionGeography,
        message,
      );
      if (transition) {
        if (!firstRealityRevealStarted) {
          firstRealityRevealStarted = true;
          setFirstRealityTransition(transition);
          setPhase('grounding');
        }
        return true;
      }
      if (firstRealityRevealStarted) return true;
      if (settleIfMissing) setPhase('empty');
      return false;
    };

    const applyObservedDecisionGeography = (
      geography: DecisionGeography | null | undefined,
    ) => {
      if (
        latestSubmitIdRef.current !== submitId
        || !isGroundedDecisionGeography(geography)
      ) return;

      const geographyChanged = shouldApplyObservedDecisionGeography({
        candidate: geography,
        baselineFingerprint: decisionGeographyFingerprint(
          decisionGeographyRef.current,
        ),
        observationId: submitId,
        latestObservationId: latestSubmitIdRef.current,
      });
      if (geographyChanged) {
        decisionGeographyRef.current = geography;
        setRestoredDecisionGeography(geography);
      }
    };

    try {
      let markWorldStateReady: (() => void) | undefined;
      const worldStateReady = new Promise<void>((resolve) => {
        markWorldStateReady = resolve;
      });
      const reconcilePersistedReality = async () => {
        const revision = ++consequenceRevision;
        const [durableProfile, durableProperties, durablePossibleLives] = await Promise.all([
          getLivingProfile(currentConversationId),
          getProperties(currentConversationId),
          getPossibleLives(currentConversationId),
        ]);
        if (latestSubmitIdRef.current !== submitId || revision !== consequenceRevision) return;
        setProfile(durableProfile);
        setProperties(durableProperties);
        setPossibleLives(durablePossibleLives);
        onPersistedRealityReconciledRef.current?.(
          currentConversationId,
          durableProperties,
        );
        applySceneResolution(durableProfile, durableProperties);
      };

      const chatCompletion = streamMessage({
        conversationId: currentConversationId,
        message,
        currentGeographicReality: currentLocation,
        onChunk: () => {},
        onWorldStateReady: () => markWorldStateReady?.(),
        onWorldConsequenceReady: (focusPropertyId, focusSubject, focusPossibleLife) => {
          onWorldConsequenceReadyRef.current?.(
            focusPropertyId,
            focusSubject,
            focusPossibleLife,
          );
          void reconcilePersistedReality().catch((error: unknown) => {
            console.error('Failed to reconcile persisted World consequence:', error);
          });
        },
      });

      await Promise.race([
        worldStateReady,
        chatCompletion.then(() => undefined),
      ]);
      const earlyRevision = consequenceRevision;
      const [nextProfile, nextProperties, decisionGeography, nextPossibleLives] = await Promise.all([
        getLivingProfile(currentConversationId),
        getProperties(currentConversationId),
        getDecisionGeography(currentConversationId),
        getPossibleLives(currentConversationId),
      ]);
      if (!conversationId) {
        skipRestoreConversationRef.current = currentConversationId;
        setConversationId(currentConversationId);
        window.history.replaceState(
          window.history.state,
          '',
          '/?conversation_id=' + encodeURIComponent(currentConversationId),
        );
      }
      if (latestSubmitIdRef.current !== submitId) return;
      if (earlyRevision === consequenceRevision) {
        setProfile(nextProfile);
        setProperties(nextProperties);
        setPossibleLives(nextPossibleLives);
        applySceneResolution(nextProfile, nextProperties, decisionGeography);
      }
      applyObservedDecisionGeography(decisionGeography);

      await chatCompletion;
      const [completedProfile, completedProperties, completedPossibleLives] = await Promise.all([
        getLivingProfile(currentConversationId),
        getProperties(currentConversationId),
        getPossibleLives(currentConversationId),
      ]);
      if (latestSubmitIdRef.current !== submitId) return;
      setProfile(completedProfile);
      setProperties(completedProperties);
      setPossibleLives(completedPossibleLives);
      applySceneResolution(completedProfile, completedProperties, undefined, true);
    } catch (error: unknown) {
      console.error('Failed to form First Reality:', error);
      if (latestSubmitIdRef.current !== submitId) return;
      try {
        const [persistedProfile, persistedProperties, persistedPossibleLives] = await Promise.all([
          getLivingProfile(currentConversationId),
          getProperties(currentConversationId),
          getPossibleLives(currentConversationId),
        ]);
        if (latestSubmitIdRef.current !== submitId) return;
        setProfile(persistedProfile);
        setProperties(persistedProperties);
        setPossibleLives(persistedPossibleLives);
        applySceneResolution(persistedProfile, persistedProperties, undefined, true);
      } catch (restoreError: unknown) {
        console.error('Failed to restore persisted World State:', restoreError);
        setPhase('empty');
      }
    }
  }, [conversationId, currentLocation]);

  const onGroundReadyChange = useCallback((ready: boolean) => {
    setGeographicGroundReady(ready);
  }, []);

  const onCameraReady = useCallback((nextReorient: FirstRealityCameraReorient) => {
    setReorient(() => nextReorient);
  }, []);

  const onGroundingSettled = useCallback(() => {
    setGroundingSettled(true);
  }, []);

  const onWorldSettled = useCallback(() => {
    setPhase((current) => current === 'revealing' ? 'formed' : current);
  }, []);

  useEffect(() => {
    if (
      phase !== 'grounding'
      || !firstRealityTransition
      || !groundingSettled
      || !geographicGroundReady
      || !reorient
    ) return;

    const frame = window.requestAnimationFrame(() => {
      reorient(
        firstRealityTransition.center,
        firstRealityTransition.worldZoom,
        null,
        placeAnchorRef.current,
      );
      setPhase('revealing');
    });
    return () => window.cancelAnimationFrame(frame);
  }, [
    firstRealityTransition,
    geographicGroundReady,
    groundingSettled,
    phase,
    reorient,
  ]);

  const authoritativeReality = useMemo(
    () => firstRealityTransition ?? resolveAuthoritativeGroundedReality(
      profile,
      properties,
      restoredDecisionGeography,
    ),
    [firstRealityTransition, profile, properties, restoredDecisionGeography],
  );
  const hasGroundedWorld = Boolean(
    authoritativeReality
    || hasAdmittedPossibleLifeReality(conversationId, properties, possibleLives),
  );
  const firstOpenActive = Boolean(submittedExpression) || !hasGroundedWorld;
  const firstOpenStage: FirstOpenRuntimeStage = phase === 'forming'
    ? 'submitting'
    : phase === 'grounding'
      ? 'grounding'
      : submittedExpression && (phase === 'revealing' || phase === 'formed')
        ? 'world'
        : 'entry';
  const worldVisible = phase === 'formed' && !submittedExpression;

  return {
    conversationId,
    profile,
    properties,
    possibleLives,
    setProperties,
    restoredDecisionGeography,
    decisionWorldActive: isGroundedDecisionGeography(restoredDecisionGeography),
    phase,
    submittedExpression,
    authoritativeReality,
    firstRealityTransition,
    currentLocation,
    hasGroundedWorld,
    firstOpenActive,
    firstOpenStage,
    worldVisible,
    geographicGroundReady,
    reorient,
    placeAnchorRef,
    submit,
    onGroundReadyChange,
    onCameraReady,
    onGroundingSettled,
    onWorldSettled,
  };
}
