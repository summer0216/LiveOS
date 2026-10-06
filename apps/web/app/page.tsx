'use client';

import { useSearchParams } from 'next/navigation';

import FirstOpenExperience, {
  FIRST_OPEN_WORLD_CAMERA_TRANSITION_MS,
} from '@/features/first-open';
import useFirstRealityRuntime from '@/features/first-reality-runtime';
import AMapGround from '@/features/living-map/AMapGround';

export default function HomePage() {
  const searchParams = useSearchParams();
  const {
    submittedExpression,
    authoritativeReality,
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

  const initialMapCenter = firstRealityTransition?.center
    ?? authoritativeReality?.center;
  const mapGround = initialMapCenter && hasGroundedWorld ? (
    <AMapGround
      initialCenter={initialMapCenter}
      initialScreenAnchorRef={firstRealityTransition ? placeAnchorRef : undefined}
      initialZoom={firstRealityTransition
        ? firstRealityTransition.focusZoom
        : authoritativeReality?.worldZoom}
      cameraTransitionDuration={firstRealityTransition
        ? FIRST_OPEN_WORLD_CAMERA_TRANSITION_MS
        : undefined}
      onGroundReadyChange={onGroundReadyChange}
      onCameraReady={onCameraReady}
    />
  ) : undefined;

  return (
    <main className="relative min-h-screen overflow-hidden bg-[#eef2ed] text-slate-950">
      {firstOpenActive ? (
        <FirstOpenExperience
          stage={firstOpenStage}
          submittedExpression={submittedExpression}
          groundedIdentity={firstRealityTransition?.identity ?? null}
          placeAnchorRef={placeAnchorRef}
          map={mapGround}
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
