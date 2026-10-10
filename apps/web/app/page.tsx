'use client';

import { useCallback, useState } from 'react';
import { useSearchParams } from 'next/navigation';

import FirstOpenExperience, {
  FIRST_OPEN_WORLD_CAMERA_TRANSITION_MS,
} from '@/features/first-open';
import RealityAnchorProjection from '@/features/possible-life-world/RealityAnchorProjection';
import useFirstRealityRuntime from '@/features/first-reality-runtime';
import AMapGround, {
  type GeographicProjection,
} from '@/features/living-map/AMapGround';

const NO_FIT_LOCATIONS: readonly { lng: number; lat: number }[] = [];

export default function HomePage() {
  const searchParams = useSearchParams();
  const {
    submittedExpression,
    currentExpressionReferent,
    phase,
    authoritativeReality,
    authoritativeProperty,
    firstRealityTransition,
    hasGroundedWorld,
    firstOpenActive,
    firstOpenStage,
    placeAnchorRef,
    submit,
    onGroundReadyChange,
    onCameraReady,
    onGroundingSettled,
    onWorldSettled,
  } = useFirstRealityRuntime({
    initialConversationId: searchParams.get('conversation_id') ?? '',
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
          submittedExpression={submittedExpression}
          groundedIdentity={authoritativeReality?.identity ?? null}
          expressionReferent={currentExpressionReferent}
          placeAnchorRef={placeAnchorRef}
          map={mapGround}
          worldProjection={(
            <RealityAnchorProjection
              identity={authoritativeProperty?.title ?? authoritativeReality?.identity ?? null}
              location={authoritativeProperty?.geographic_status === 'GROUNDED'
                && typeof authoritativeProperty.lng === 'number'
                && typeof authoritativeProperty.lat === 'number'
                ? { lng: authoritativeProperty.lng, lat: authoritativeProperty.lat }
                : null}
              projection={mapProjection}
              zoom={mapZoom}
              visible={firstOpenStage === 'world' && phase !== 'empty'}
            />
          )}
          onSubmit={(expression) => {
            void submit(expression);
          }}
          onGroundingSettled={onGroundingSettled}
          onWorldSettled={onWorldSettled}
        />
      ) : mapGround}
    </main>
  );
}
