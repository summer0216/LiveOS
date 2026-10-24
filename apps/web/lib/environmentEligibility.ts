import type { PlaceContextAdmission, PlaceContextEvidence } from '../services/property';

export interface EnvironmentEligibilityResult {
  conversation_id: string;
  source_user_turn_id: number;
  items: Array<{
    attention: {
      conversation_id: string;
      source_user_turn_id: number;
      source_quote: string;
      property_id: string;
      property_identity: string;
      property_lng: number;
      property_lat: number;
      category: string;
      type_codes: string[];
      place_binding_source: 'USER_ATTENTION' | 'FOCUS';
    };
    environment_external_id: string;
    environment_identity: string;
    environment_type_code: string;
    evidence: PlaceContextEvidence;
    admission: PlaceContextAdmission;
    relevance_basis: 'USER_EXPRESSED_CATEGORY' | 'RELATED_RAIL_SUPPLEMENT';
  }>;
}

const record = (value: unknown): value is Record<string, unknown> => (
  typeof value === 'object' && value !== null
);
const text = (value: unknown): value is string => typeof value === 'string' && value.trim().length > 0;
const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);

/** Transport shape validation only. Reality admission remains authoritative on the backend. */
export function isEnvironmentEligibilityResult(value: unknown): value is EnvironmentEligibilityResult {
  if (!record(value) || !text(value.conversation_id)
    || !Number.isSafeInteger(value.source_user_turn_id)
    || (value.source_user_turn_id as number) <= 0 || !Array.isArray(value.items)) return false;
  return value.items.every((item) => {
    if (!record(item) || !record(item.attention) || !record(item.evidence)
      || !record(item.admission)) return false;
    const { attention, evidence, admission } = item;
    return attention.conversation_id === value.conversation_id
      && attention.source_user_turn_id === value.source_user_turn_id
      && text(attention.source_quote) && text(attention.property_id)
      && text(attention.property_identity) && finite(attention.property_lng)
      && finite(attention.property_lat) && text(attention.category)
      && Array.isArray(attention.type_codes) && attention.type_codes.length > 0
      && attention.type_codes.every(text)
      && (attention.place_binding_source === 'FOCUS' || attention.place_binding_source === 'USER_ATTENTION')
      && text(item.environment_external_id) && text(item.environment_identity)
      && text(item.environment_type_code)
      && (item.relevance_basis === 'USER_EXPRESSED_CATEGORY' || item.relevance_basis === 'RELATED_RAIL_SUPPLEMENT')
      && text(evidence.source_provider) && text(evidence.source_reference)
      && text(evidence.source_record_id) && text(evidence.identity) && text(evidence.observed_at)
      && admission.status === 'ADMITTED' && text(admission.admitted_at)
      && text(admission.property_id) && text(admission.property_identity)
      && finite(admission.property_lng) && finite(admission.property_lat)
      && text(admission.evidence_reference) && text(admission.evidence_observed_at)
      && text(admission.authority);
  });
}
