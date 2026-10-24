import type { EnvironmentEligibilityResult } from '../../../web/lib/environmentEligibility';
import type { PlaceContextAdmission, PlaceContextEvidence, Property } from '../../../web/services/property';
import type { GroundedPlace } from './groundedPlace';

export interface ProjectedEnvironment {
  id: string;
  name: string;
  center: { lng: number; lat: number };
  category: string;
  typeCode: string;
  sourceUserTurnId: number;
  relevance: 'USER_EXPRESSED_CATEGORY' | 'RELATED_RAIL_SUPPLEMENT';
  distanceM: number | null;
  walkingMinutes: number | null;
  evidence: PlaceContextEvidence;
}

function boundToPlace(admission: PlaceContextAdmission, place: GroundedPlace) {
  return admission.status === 'ADMITTED' && admission.property_id === place.propertyId
    && admission.property_identity === place.identity
    && admission.property_lng === place.center.lng && admission.property_lat === place.center.lat;
}

/** Join SSE eligibility to its authoritative coordinates; never project the POI list itself. */
export function selectEnvironmentProjection(
  place: GroundedPlace | null,
  properties: readonly Property[] = [],
  eligibility?: EnvironmentEligibilityResult | null,
): ProjectedEnvironment[] {
  if (!place || !eligibility || eligibility.conversation_id !== place.conversationId) return [];
  const property = properties.find((item) => item.id === place.propertyId
    && item.conversation_id === place.conversationId && item.geographic_status === 'GROUNDED'
    && item.geographic_identity === place.identity && item.lng === place.center.lng && item.lat === place.center.lat);
  if (!property) return [];
  const result: ProjectedEnvironment[] = [];
  const seen = new Set<string>();
  for (const item of eligibility.items) {
    const attention = item.attention;
    if (attention.conversation_id !== place.conversationId
      || attention.source_user_turn_id !== eligibility.source_user_turn_id
      || attention.property_id !== place.propertyId || attention.property_identity !== place.identity
      || attention.property_lng !== place.center.lng || attention.property_lat !== place.center.lat
      || !boundToPlace(item.admission, place) || seen.has(item.environment_external_id)) continue;
    const sources = (property.place_context ?? []).filter((source) => source.external_id === item.environment_external_id);
    if (sources.length !== 1) continue;
    const source = sources[0];
    if (!source.name.trim() || source.category !== attention.category || source.structure_version !== 3 || !boundToPlace(source.admission, place)
      || source.identity !== item.environment_identity || source.type_code !== item.environment_type_code
      || source.evidence.source_record_id !== item.environment_external_id
      || item.evidence.source_record_id !== source.external_id
      || source.evidence.identity !== source.identity
      || source.evidence.identity !== item.evidence.identity
      || source.evidence.source_provider !== item.evidence.source_provider
      || source.evidence.source_reference !== item.evidence.source_reference
      || source.evidence.observed_at !== item.evidence.observed_at
      || source.admission.evidence_reference !== item.admission.evidence_reference
      || source.admission.evidence_observed_at !== item.admission.evidence_observed_at
      || !Number.isFinite(source.lng) || !Number.isFinite(source.lat)
      || Math.abs(source.lng) > 180 || Math.abs(source.lat) > 90) continue;
    const walking = source.walking_evidence && source.walking_admission
      && boundToPlace(source.walking_admission, place)
      && source.walking_admission.evidence_reference === source.walking_evidence.source_reference
      && source.walking_admission.evidence_observed_at === source.walking_evidence.observed_at;
    seen.add(item.environment_external_id);
    result.push({
      id: source.external_id, name: source.name, center: { lng: source.lng, lat: source.lat },
      category: source.category, typeCode: source.type_code, sourceUserTurnId: eligibility.source_user_turn_id,
      relevance: item.relevance_basis, evidence: source.evidence,
      distanceM: Number.isFinite(source.distance_m) && source.distance_m >= 0 ? source.distance_m : null,
      walkingMinutes: walking && Number.isInteger(source.walking_minutes) && source.walking_minutes! > 0
        ? source.walking_minutes : null,
    });
  }
  return result;
}
