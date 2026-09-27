type GroundedConversationHome = {
  id: string;
  conversation_id: string;
  provenance?: string;
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
