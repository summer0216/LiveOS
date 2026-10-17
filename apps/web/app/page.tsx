'use client';

import { useCallback, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';

import UnifiedSurface from '@/features/unified-surface';
import useFirstRealityRuntime from '@/features/first-reality-runtime';
import AMapGround from '@/features/living-map/AMapGround';
import { FIRST_OPEN_WORLD_CAMERA_TRANSITION_MS, type GeographicProjection } from '@/lib/runtimePresentationContract';
import type { WorldConsequenceFocus } from '@/lib/worldConsequence';

const NO_FIT_LOCATIONS: readonly { lng: number; lat: number }[] = [];

export default function HomePage() {
  const searchParams = useSearchParams();
  const placeAnchorRef = useRef<HTMLSpanElement>(null);
  const [consequenceFocus, setConsequenceFocus] = useState<WorldConsequenceFocus | null>(null);
  const onWorldConsequenceReady = useCallback((
    focusPropertyId?: WorldConsequenceFocus['focusPropertyId'],
    focusSubject?: WorldConsequenceFocus['focusSubject'],
    focusPossibleLife?: WorldConsequenceFocus['focusPossibleLife'],
  ) => {
    setConsequenceFocus(focusPropertyId || focusSubject || focusPossibleLife
      ? { focusPropertyId, focusSubject, focusPossibleLife } : null);
  }, []);
  const {
    messages,
    isResponding,
    isRestoringConversation,
    conversationError,
    isSubmittingExpression,
    phase,
    authoritativeReality,
    firstRealityTransition,
    hasGroundedWorld,
    geographicGroundReady,
    reorient,
    submit,
    onGroundReadyChange,
    onCameraReady,
    onWorldSettled,
  } = useFirstRealityRuntime({
    initialConversationId: searchParams.get('conversation_id') ?? '',
    placeAnchorRef,
    onWorldConsequenceReady,
  });
  const [mapProjection, setMapProjection] = useState<GeographicProjection | null>(null);
  const [mapZoom, setMapZoom] = useState<number | null>(null);
  const handleProjectionReady = useCallback((projection: GeographicProjection) => {
    setMapProjection(() => projection);
  }, []);
  const handleZoomChange = useCallback((zoom: number) => {
    setMapZoom(zoom);
  }, []);
  const initialMapCenter = firstRealityTransition?.center
    ?? authoritativeReality?.center;
  const mapGround = initialMapCenter && hasGroundedWorld ? (
    <AMapGround
      fitLocations={NO_FIT_LOCATIONS}
      initialCenter={initialMapCenter}
      initialScreenAnchorRef={authoritativeReality ? placeAnchorRef : undefined}
      initialZoom={firstRealityTransition
        ? firstRealityTransition.focusZoom
        : undefined}
      initialFraming={!firstRealityTransition
        ? authoritativeReality?.worldFraming
        : undefined}
      cameraTransitionDuration={firstRealityTransition
        ? FIRST_OPEN_WORLD_CAMERA_TRANSITION_MS
        : undefined}
      onGroundReadyChange={onGroundReadyChange}
      onCameraReady={onCameraReady}
      onProjectionReady={handleProjectionReady}
      onZoomChange={handleZoomChange}
    />
  ) : undefined;

  return (
    <main className="relative min-h-screen overflow-hidden bg-[#eef2ed] text-slate-950">
      <UnifiedSurface
        requiresCameraAnchor={phase === 'grounding' || phase === 'revealing' || phase === 'formed'}
        revealStarted={phase === 'revealing' || phase === 'formed'}
        revealComplete={phase === 'formed'}
        geographicGroundReady={geographicGroundReady}
        cameraReady={reorient !== null}
        groundedReality={authoritativeReality}
        consequenceFocus={consequenceFocus}
        messages={messages}
        isResponding={isResponding}
        isSubmittingExpression={isSubmittingExpression}
        isRestoringConversation={isRestoringConversation}
        conversationError={conversationError}
        placeAnchorRef={placeAnchorRef}
        map={mapGround}
        mapProjection={mapProjection}
        mapZoom={mapZoom}
        onSubmit={submit}
        onWorldSettled={onWorldSettled}
      />
    </main>
  );
}
