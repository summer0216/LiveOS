import { homeViewport, type GeographicCameraFraming } from '../../../web/lib/geographicScaleContract.ts';
import type { Property } from '../../infrastructure/groundedRealityApi';

type GroundingFields = Pick<Property,
  | 'conversation_id'
  | 'provenance'
  | 'decision_state'
  | 'title'
  | 'geographic_identity'
  | 'geographic_precision'
  | 'geographic_status'
  | 'lng'
  | 'lat'
>;

export interface GroundedPlace {
  conversationId: string;
  identity: string;
  name: string | null;
  center: { lng: number; lat: number };
  framing: GeographicCameraFraming;
}

export function selectGroundedPlace(
  conversationId: string,
  properties: readonly GroundingFields[],
): GroundedPlace | null {
  const property = [...properties].reverse().find((item) => (
    item.conversation_id === conversationId
    && item.provenance === 'USER_PROVIDED'
    && item.decision_state === 'ACTIVE'
    && Boolean(item.geographic_identity?.trim())
    && homeViewport(item, 'SEE') !== null
  ));
  if (!property) return null;
  const viewport = homeViewport(property, 'SEE');
  if (!viewport) return null;
  return {
    conversationId,
    identity: property.geographic_identity!.trim(),
    name: property.title?.trim() || null,
    center: viewport.center,
    framing: viewport.framing,
  };
}
