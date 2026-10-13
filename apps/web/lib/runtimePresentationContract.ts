import type { RefObject } from 'react';
import type { GeographicCameraFraming } from './geographicScaleContract';

export type FirstOpenRuntimeStage = 'entry' | 'submitting' | 'grounding' | 'world';

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
