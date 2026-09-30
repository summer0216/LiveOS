import type { Property } from '@/services/property';
import type { PossibleLifeWorldState } from '@/services/possibleLife';

export interface ProjectedPossibleLife {
  possibleLife: PossibleLifeWorldState;
  residence: Property & { lng: number; lat: number };
}

export function resolvePossibleLifeWorld(
  possibleLives: PossibleLifeWorldState[],
  properties: Property[],
): ProjectedPossibleLife[] {
  return possibleLives.flatMap((possibleLife) => {
    const residence = properties.find(
      property => property.id === possibleLife.residence_property_id,
    );
    if (
      !residence
      || residence.geographic_status !== 'GROUNDED'
      || typeof residence.lng !== 'number'
      || typeof residence.lat !== 'number'
      || possibleLife.living_time.residence_property_id !== residence.id
      || possibleLife.living_time_residence_property_id !== residence.id
      || possibleLife.living_time.work_subject_identity
        !== possibleLife.work_subject.identity
      || possibleLife.living_time.work_geographic_identity
        !== possibleLife.work_subject.geographic_identity
    ) return [];
    return [{ possibleLife, residence: residence as Property & { lng: number; lat: number } }];
  });
}
