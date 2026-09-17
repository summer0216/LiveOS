import type { DecisionGeography } from '@/services/decisionGeography';

export function isGroundedDecisionGeography(
  geography: DecisionGeography | null | undefined,
): geography is DecisionGeography & { lng: number; lat: number } {
  return Boolean(
    geography?.intent_established
    && geography.status === 'GROUNDED'
    && typeof geography.lng === 'number'
    && typeof geography.lat === 'number',
  );
}

export function decisionGeographyFingerprint(
  geography: DecisionGeography | null | undefined,
): string | null {
  if (!isGroundedDecisionGeography(geography)) return null;

  return [
    geography.conversation_id,
    geography.identity,
    geography.geographic_scope ?? '',
    geography.lng,
    geography.lat,
  ].join('|');
}

export function shouldApplyObservedDecisionGeography({
  candidate,
  baselineFingerprint,
  observationId,
  latestObservationId,
}: {
  candidate: DecisionGeography | null | undefined;
  baselineFingerprint: string | null;
  observationId: number;
  latestObservationId: number;
}): boolean {
  return observationId === latestObservationId
    && isGroundedDecisionGeography(candidate)
    && decisionGeographyFingerprint(candidate) !== baselineFingerprint;
}
