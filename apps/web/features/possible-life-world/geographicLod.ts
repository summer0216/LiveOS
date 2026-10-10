import { GEOGRAPHIC_SCALE_CONTRACT } from '@/lib/geographicScaleContract';

export const WORLD_GEOGRAPHIC_LOD = {
  LOCAL: 'local',
  DISTRICT: 'district',
  REGIONAL: 'regional',
} as const;

export type WorldGeographicLod = typeof WORLD_GEOGRAPHIC_LOD[keyof typeof WORLD_GEOGRAPHIC_LOD];

const LOCAL_MIN_ZOOM = GEOGRAPHIC_SCALE_CONTRACT.PLACE.SEE - 1;
const REGIONAL_MAX_ZOOM = GEOGRAPHIC_SCALE_CONTRACT.CITY.FOCUS;

export function resolveWorldGeographicLod(zoom: number | null): WorldGeographicLod {
  if (zoom === null || !Number.isFinite(zoom)) return WORLD_GEOGRAPHIC_LOD.LOCAL;
  if (zoom >= LOCAL_MIN_ZOOM) return WORLD_GEOGRAPHIC_LOD.LOCAL;
  if (zoom > REGIONAL_MAX_ZOOM) return WORLD_GEOGRAPHIC_LOD.DISTRICT;
  return WORLD_GEOGRAPHIC_LOD.REGIONAL;
}
