export interface WorkSubjectFocus {
  identity: string;
  geographic_identity: string;
  geographic_precision: 'PLACE';
  geographic_status: 'GROUNDED';
  lng: number;
  lat: number;
  relationship: 'WORK';
}

export interface WorldConsequenceFocus {
  focusPropertyId?: string;
  focusSubject?: WorkSubjectFocus;
  focusPossibleLife?: PossibleLifeFocus;
}

export interface PossibleLifeFocus {
  possible_life: {
    id: string;
    work_subject_owner_id: string;
    residence_property_id: string;
    living_time_residence_property_id: string;
    personal_meaning_reference: string;
  };
  personal_meaning: {
    id: string;
    possible_life_id: string;
    meaning: string;
    living_time_residence_property_id: string;
    actual_travel_minutes: number;
    actual_travel_mode: 'WALKING' | 'PUBLIC_TRANSIT';
    route_evidence_source: string;
    route_evidence_reference: string;
    requirement_reference: string;
    maximum_commute_minutes: number;
    requirement_satisfied: boolean;
  };
}

function isWorkSubjectFocus(value: unknown): value is WorkSubjectFocus {
  if (typeof value !== 'object' || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.identity === 'string'
    && typeof candidate.geographic_identity === 'string'
    && candidate.geographic_precision === 'PLACE'
    && candidate.geographic_status === 'GROUNDED'
    && typeof candidate.lng === 'number'
    && Number.isFinite(candidate.lng)
    && typeof candidate.lat === 'number'
    && Number.isFinite(candidate.lat)
    && candidate.relationship === 'WORK'
  );
}

function isPossibleLifeFocus(value: unknown): value is PossibleLifeFocus {
  if (typeof value !== 'object' || value === null) return false;
  const candidate = value as Record<string, unknown>;
  if (
    typeof candidate.possible_life !== 'object'
    || candidate.possible_life === null
    || typeof candidate.personal_meaning !== 'object'
    || candidate.personal_meaning === null
  ) return false;
  const possibleLife = candidate.possible_life as Record<string, unknown>;
  const meaning = candidate.personal_meaning as Record<string, unknown>;
  return (
    typeof possibleLife.id === 'string'
    && typeof possibleLife.work_subject_owner_id === 'string'
    && typeof possibleLife.residence_property_id === 'string'
    && typeof possibleLife.living_time_residence_property_id === 'string'
    && typeof possibleLife.personal_meaning_reference === 'string'
    && typeof meaning.id === 'string'
    && meaning.possible_life_id === possibleLife.id
    && typeof meaning.meaning === 'string'
    && meaning.living_time_residence_property_id
      === possibleLife.living_time_residence_property_id
    && typeof meaning.actual_travel_minutes === 'number'
    && Number.isFinite(meaning.actual_travel_minutes)
    && (meaning.actual_travel_mode === 'WALKING'
      || meaning.actual_travel_mode === 'PUBLIC_TRANSIT')
    && typeof meaning.route_evidence_source === 'string'
    && typeof meaning.route_evidence_reference === 'string'
    && meaning.requirement_reference === possibleLife.personal_meaning_reference
    && typeof meaning.maximum_commute_minutes === 'number'
    && Number.isFinite(meaning.maximum_commute_minutes)
    && typeof meaning.requirement_satisfied === 'boolean'
  );
}

export function parseWorldConsequence(
  value: unknown,
): WorldConsequenceFocus | null {
  if (value === true) return {};
  if (typeof value !== 'object' || value === null) return null;

  const focusPropertyId = 'focus_property_id' in value
    && typeof value.focus_property_id === 'string'
    ? value.focus_property_id : undefined;
  const focusSubject = 'focus_subject' in value
    && isWorkSubjectFocus(value.focus_subject)
    ? value.focus_subject : undefined;
  const focusPossibleLife = 'focus_possible_life' in value
    && isPossibleLifeFocus(value.focus_possible_life)
    ? value.focus_possible_life : undefined;
  const propertyTargetIsValid = !('focus_property_id' in value)
    || focusPropertyId !== undefined;
  const subjectTargetIsValid = !('focus_subject' in value)
    || focusSubject !== undefined;
  const possibleLifeTargetIsValid = !('focus_possible_life' in value)
    || focusPossibleLife !== undefined;
  if (
    !propertyTargetIsValid
    || !subjectTargetIsValid
    || !possibleLifeTargetIsValid
    || (
      focusPropertyId === undefined
      && focusSubject === undefined
      && focusPossibleLife === undefined
    )
  ) return null;

  return { focusPropertyId, focusSubject, focusPossibleLife };
}
