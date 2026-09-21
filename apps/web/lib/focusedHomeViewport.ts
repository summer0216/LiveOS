import type { Property } from '@/services/property';

const FOCUSED_HOME_ZOOM = 15;

/** A single grounded Home can frame its surrounding neighborhood. */
export function focusedHomeViewport(
  home: Pick<Property, 'geographic_status' | 'lng' | 'lat'> | null | undefined,
): { center: { lng: number; lat: number }; zoom: number } | null {
  if (
    home?.geographic_status !== 'GROUNDED'
    || typeof home.lng !== 'number' || !Number.isFinite(home.lng)
    || Math.abs(home.lng) > 180
    || typeof home.lat !== 'number' || !Number.isFinite(home.lat)
    || Math.abs(home.lat) > 90
  ) {
    return null;
  }

  return { center: { lng: home.lng, lat: home.lat }, zoom: FOCUSED_HOME_ZOOM };
}
