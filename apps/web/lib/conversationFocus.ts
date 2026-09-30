import type { WorkSubjectFocus } from './worldConsequence';

type GroundedConversationHome = {
  id: string;
  conversation_id: string;
  provenance?: string;
  geographic_status: string;
  lng: number | null;
  lat: number | null;
};

type GroundedWorkReality = {
  work_location: string | null;
  geographic_identity: string | null;
  geographic_precision: string | null;
  geographic_status: string;
  lng: number | null;
  lat: number | null;
};

export function applyGroundedConversationFocus(
  propertyId: string | undefined,
  conversationId: string,
  properties: GroundedConversationHome[],
  focusChoice: (propertyId: string) => void,
): boolean {
  if (!propertyId || !properties.some((property) =>
    property.id === propertyId
    && property.conversation_id === conversationId
    && property.provenance === 'USER_PROVIDED'
    && property.geographic_status === 'GROUNDED'
    && typeof property.lng === 'number' && Number.isFinite(property.lng)
    && typeof property.lat === 'number' && Number.isFinite(property.lat)
  )) return false;
  focusChoice(propertyId);
  return true;
}

export function resolveWorkSubjectProjectionFocus(
  subject: WorkSubjectFocus | null,
  work: GroundedWorkReality | null,
): WorkSubjectFocus | null {
  if (
    subject === null
    || work === null
    || work.geographic_status !== 'GROUNDED'
    || work.geographic_precision !== 'PLACE'
    || work.work_location?.trim() !== subject.identity
    || work.geographic_identity !== subject.geographic_identity
    || work.lng !== subject.lng
    || work.lat !== subject.lat
  ) return null;

  return subject;
}
