import type { PlaceContextReality, Property } from '@/services/property';

export type AdmittedPlaceContextReality = Extract<
  PlaceContextReality,
  { structure_version: 3 }
>;

export function groundedPlaceContextScope(
  conversationId: string,
  property: Property | null,
): string | null {
  if (
    !conversationId
    || !property?.id
    || property.conversation_id !== conversationId
    || property.provenance !== 'USER_PROVIDED'
    || property.geographic_status !== 'GROUNDED'
    || !property.geographic_identity
    || typeof property.lng !== 'number'
    || !Number.isFinite(property.lng)
    || typeof property.lat !== 'number'
    || !Number.isFinite(property.lat)
  ) return null;

  return JSON.stringify([
    conversationId,
    property.id,
    property.geographic_identity,
    property.lng,
    property.lat,
  ]);
}

export function admittedPlaceContextFor(
  property: Property | null,
): AdmittedPlaceContextReality[] {
  if (!property) return [];
  return (property.place_context ?? []).filter(
    (reality): reality is AdmittedPlaceContextReality => (
      reality.structure_version === 3
      && reality.admission?.status === 'ADMITTED'
      && reality.admission.property_id === property.id
      && reality.admission.property_identity === property.geographic_identity
      && reality.admission.property_lng === property.lng
      && reality.admission.property_lat === property.lat
    ),
  );
}

export function hasCompleteAdmittedPlaceContext(
  property: Property | null,
  admitted: readonly AdmittedPlaceContextReality[] = admittedPlaceContextFor(property),
): boolean {
  return Boolean(property?.place_context?.length)
    && admitted.length === property?.place_context?.length;
}

export function requestPlaceContextOnce(
  attempts: Map<string, Promise<Property[]>>,
  scope: string,
  acquireAndReread: () => Promise<Property[]>,
): Promise<Property[]> {
  const existing = attempts.get(scope);
  if (existing) return existing;
  const request = acquireAndReread();
  attempts.set(scope, request);
  void request.catch(() => {
    if (attempts.get(scope) === request) attempts.delete(scope);
  });
  return request;
}

export function reconcileRereadPlaceContext(
  current: Property[],
  persisted: Property,
  conversationId: string,
  scope: string,
): Property[] {
  if (groundedPlaceContextScope(conversationId, persisted) !== scope) return current;
  return current.map((property) => (
    groundedPlaceContextScope(conversationId, property) === scope
      ? { ...property, place_context: persisted.place_context }
      : property
  ));
}
