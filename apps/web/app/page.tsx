'use client';

import { useCallback, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';

import FirstOpenExperience, {
  FIRST_OPEN_WORLD_CAMERA_TRANSITION_MS,
} from '@/features/first-open';
import RealityAnchorProjection from '@/features/possible-life-world/RealityAnchorProjection';
import useFirstRealityRuntime from '@/features/first-reality-runtime';
import AMapGround from '@/features/living-map/AMapGround';
import type { GeographicProjection } from '@/lib/runtimePresentationContract';

const NO_FIT_LOCATIONS: readonly { lng: number; lat: number }[] = [];

export default function HomePage() {
  const searchParams = useSearchParams();
  const placeAnchorRef = useRef<HTMLSpanElement>(null);
  const {
    submittedExpression,
    isSubmittingExpression,
    currentExpressionReferent,
    phase,
    authoritativeReality,
    firstRealityTransition,
    hasGroundedWorld,
    firstOpenActive,
    firstOpenStage,
    submit,
    onGroundReadyChange,
    onCameraReady,
    onWorldSettled,
  } = useFirstRealityRuntime({
    initialConversationId: searchParams.get('conversation_id') ?? '',
    placeAnchorRef,
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
      {firstOpenActive ? (
        <FirstOpenExperience
          stage={firstOpenStage}
          worldFormed={phase === 'formed'}
          isSubmittingExpression={isSubmittingExpression}
          submittedExpression={submittedExpression}
          groundedIdentity={authoritativeReality?.identity ?? null}
          expressionReferent={currentExpressionReferent}
          placeAnchorRef={placeAnchorRef}
          map={mapGround}
          worldProjection={(
            <RealityAnchorProjection
              identity={authoritativeReality?.identity ?? null}
              location={authoritativeReality?.center ?? null}
              projection={mapProjection}
              zoom={mapZoom}
              visible={firstOpenStage === 'world' && phase !== 'empty'}
            />
          )}
          onSubmit={submit}
          onWorldSettled={onWorldSettled}
        />
      ) : mapGround}
    </main>
  );
}
