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
  const propertyTargetIsValid = !('focus_property_id' in value)
    || focusPropertyId !== undefined;
  const subjectTargetIsValid = !('focus_subject' in value)
    || focusSubject !== undefined;
  if (
    !propertyTargetIsValid
    || !subjectTargetIsValid
    || (focusPropertyId === undefined && focusSubject === undefined)
  ) return null;

  return { focusPropertyId, focusSubject };
}
