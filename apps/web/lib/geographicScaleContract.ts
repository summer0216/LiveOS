import type { DecisionGeography } from '@/services/decisionGeography';
import type { GeographicPrecision } from '@/services/profile';
import type { Property } from '@/services/property';

export type GeographicRealityLevel =
  | 'COUNTRY'
  | 'PROVINCE'
  | 'CITY'
  | 'DISTRICT'
  | 'AREA'
  | 'PLACE'
  | 'RESIDENCE'
  | 'EXACT';

export type GeographicAttention = 'SEE' | 'FOCUS';

export interface GeographicCameraFraming {
  level: GeographicRealityLevel;
  attention: GeographicAttention;
}

export interface MapViewportSize {
  width: number;
  height: number;
  insets?: Partial<MapViewportInsets>;
}

export interface MapViewportInsets {
  top: number;
  right: number;
  bottom: number;
  left: number;
}

export const GEOGRAPHIC_SCALE_CONTRACT: Record<
  GeographicRealityLevel,
  Record<GeographicAttention, number>
> = {
  COUNTRY: { SEE: 4.5, FOCUS: 6 },
  PROVINCE: { SEE: 6.5, FOCUS: 8 },
  CITY: { SEE: 10.5, FOCUS: 12 },
  DISTRICT: { SEE: 12.5, FOCUS: 14 },
  AREA: { SEE: 13.5, FOCUS: 15 },
  PLACE: { SEE: 16, FOCUS: 16 },
  RESIDENCE: { SEE: 17, FOCUS: 17 },
  EXACT: { SEE: 17, FOCUS: 18 },
};

const FOCUS_SUBJECT_PROMINENCE: Partial<Record<GeographicRealityLevel, number>> = {
  PLACE: 1.7,
  RESIDENCE: 1.5,
};

export function geographicScaleZoom(
  level: GeographicRealityLevel,
  attention: GeographicAttention,
) {
  return GEOGRAPHIC_SCALE_CONTRACT[level][attention];
}

export function isViewportAdaptiveLevel(level: GeographicRealityLevel) {
  return level === 'PLACE' || level === 'RESIDENCE';
}

export function geographicZoomForViewport(
  framing: GeographicCameraFraming,
  viewport: MapViewportSize,
) {
  const baseZoom = geographicScaleZoom(framing.level, framing.attention);
  if (!isViewportAdaptiveLevel(framing.level)) return baseZoom;
  if (
    !Number.isFinite(viewport.width) || viewport.width <= 0
    || !Number.isFinite(viewport.height) || viewport.height <= 0
  ) return baseZoom;

  const insets = normalizedInsets(viewport);
  const usableWidth = Math.max(1, viewport.width - insets.left - insets.right);
  const usableHeight = Math.max(1, viewport.height - insets.top - insets.bottom);
  const shortEdge = Math.min(usableWidth, usableHeight);
  if (!Number.isFinite(shortEdge) || shortEdge <= 0) return baseZoom;

  const viewportAdjustment = Math.max(
    -0.75,
    Math.min(0.75, Math.log2(shortEdge / 800)),
  );
  const presentationAdjustment = framing.attention === 'FOCUS'
    ? Math.max(
        0,
        Math.min(
          0.75,
          Math.log2(
            (viewport.width * viewport.height) / (usableWidth * usableHeight),
          ),
        ),
      )
    : 0;
  const subjectAdjustment = framing.attention === 'FOCUS'
    ? Math.log2(FOCUS_SUBJECT_PROMINENCE[framing.level] ?? 1)
    : 0;
  return Math.round(
    (
      baseZoom
      + viewportAdjustment
      + presentationAdjustment
      + subjectAdjustment
    ) * 4,
  ) / 4;
}

function normalizedInsets(viewport: MapViewportSize): MapViewportInsets {
  const inset = (value: number | undefined, extent: number) => (
    Number.isFinite(value) ? Math.max(0, Math.min(value ?? 0, extent - 1)) : 0
  );
  return {
    top: inset(viewport.insets?.top, viewport.height),
    right: inset(viewport.insets?.right, viewport.width),
    bottom: inset(viewport.insets?.bottom, viewport.height),
    left: inset(viewport.insets?.left, viewport.width),
  };
}

export function geographicCameraCenterForViewport(
  anchor: { lng: number; lat: number },
  zoom: number,
  viewport: MapViewportSize,
) {
  const insets = normalizedInsets(viewport);
  const desiredX = insets.left
    + (viewport.width - insets.left - insets.right) / 2;
  const desiredY = insets.top
    + (viewport.height - insets.top - insets.bottom) / 2;
  const worldSize = 256 * (2 ** zoom);
  const latitude = Math.max(-85.05112878, Math.min(85.05112878, anchor.lat));
  const sine = Math.sin(latitude * Math.PI / 180);
  const anchorX = (anchor.lng + 180) / 360 * worldSize;
  const anchorY = (
    0.5 - Math.log((1 + sine) / (1 - sine)) / (4 * Math.PI)
  ) * worldSize;
  const centerX = anchorX + viewport.width / 2 - desiredX;
  const centerY = anchorY + viewport.height / 2 - desiredY;
  const longitude = centerX / worldSize * 360 - 180;
  const mercator = Math.PI * (1 - 2 * centerY / worldSize);
  const latitudeAtCenter = 180 / Math.PI * Math.atan(Math.sinh(mercator));
  return { lng: longitude, lat: latitudeAtCenter };
}

export function realityLevelForDecisionScope(
  scope: DecisionGeography['geographic_scope'],
): GeographicRealityLevel {
  if (scope === 'REGION') return 'PROVINCE';
  if (scope === 'LOCAL') return 'AREA';
  return 'CITY';
}

export function realityLevelForPrecision(
  precision: GeographicPrecision,
): GeographicRealityLevel {
  if (precision === 'COMMUNITY') return 'RESIDENCE';
  if (precision === 'STREET') return 'PLACE';
  return precision;
}

export function decisionGeographyZoom(
  geography: Pick<DecisionGeography, 'geographic_scope'>,
  attention: GeographicAttention = 'SEE',
) {
  return geographicScaleZoom(
    realityLevelForDecisionScope(geography.geographic_scope),
    attention,
  );
}

type GroundedHome = Pick<
  Property,
  'geographic_status' | 'geographic_precision' | 'lng' | 'lat'
> | null | undefined;

function validHomeCenter(home: GroundedHome) {
  if (
    home?.geographic_status !== 'GROUNDED'
    || typeof home.lng !== 'number' || !Number.isFinite(home.lng)
    || Math.abs(home.lng) > 180
    || typeof home.lat !== 'number' || !Number.isFinite(home.lat)
    || Math.abs(home.lat) > 90
  ) {
    return null;
  }
  return { lng: home.lng, lat: home.lat };
}

export function homeViewport(
  home: GroundedHome,
  attention: GeographicAttention,
): {
  center: { lng: number; lat: number };
  framing: GeographicCameraFraming;
} | null {
  const center = validHomeCenter(home);
  if (!center || !home?.geographic_precision) return null;
  return {
    center,
    framing: {
      level: realityLevelForPrecision(home.geographic_precision),
      attention,
    },
  };
}
