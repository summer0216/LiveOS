import type { RefObject } from 'react';
import type { GeographicCameraFraming } from './geographicScaleContract';

export type FirstOpenRuntimeStage = 'entry' | 'submitting' | 'grounding' | 'world';

// Existing First Open camera/reveal durations, shared by replacement presentations.
export const FIRST_OPEN_WORLD_CAMERA_TRANSITION_MS = 2800;
export const WORLD_SETTLE_MS = 3200;

export interface ConversationMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

export interface GeographicProjection {
  (location: { lng: number; lat: number }): { x: number; y: number };
}

export type GeographicCameraTarget = number | GeographicCameraFraming;

export type GeographicCameraReorient = (
  center: { lng: number; lat: number },
  target: GeographicCameraTarget,
  occlusion?: HTMLElement | null,
  screenAnchor?: HTMLElement | null,
) => void;

/** Presentation owns the mounted screen anchor; Runtime only reads it for framing. */
export interface WorldPresentationAnchor<T extends HTMLElement = HTMLElement> {
  placeAnchorRef: RefObject<T | null>;
}

export interface WorldRevealPresentation<T extends HTMLElement = HTMLElement>
  extends WorldPresentationAnchor<T> {
  /** Presentation reports reveal completion using its existing completion rule. */
  onWorldSettled: () => void;
}

/** Admitted Reality details used by presentation; admission remains Runtime-owned. */
export interface GroundedRealityPresentation {
  identity: string;
  center: { lng: number; lat: number };
}

/** Independent readiness facts, mapped at the page boundary; no presentation-owned lifecycle. */
export interface WorldPresentationReadiness {
  geographicGroundReady: boolean;
  cameraReady: boolean;
  /** Runtime needs a screen anchor for initial camera alignment and subsequent continuity. */
  requiresCameraAnchor: boolean;
  /** Initial camera alignment has handed off to the existing world reveal. */
  revealStarted: boolean;
  /** Runtime has accepted reveal completion, including a restored formed World. */
  revealComplete: boolean;
}
