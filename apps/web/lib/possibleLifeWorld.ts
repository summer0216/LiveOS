import type { Property } from '@/services/property';
import type { PossibleLifeWorldState } from '@/services/possibleLife';
import type { PossibleLifeFocus } from '@/lib/worldConsequence';

export interface ProjectedPossibleLife {
  possibleLife: PossibleLifeWorldState;
  residence: Property & { lng: number; lat: number };
}

export interface ProjectedPossibleLifeFocus {
  projectedPossibleLife: ProjectedPossibleLife;
  personalMeaning: PossibleLifeFocus['personal_meaning'];
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

export function resolvePossibleLifeProjectionFocus(
  focus: PossibleLifeFocus | null,
  projectedPossibleLives: ProjectedPossibleLife[],
): ProjectedPossibleLifeFocus | null {
  if (!focus) return null;
  const identity = focus.possible_life;
  const projectedPossibleLife = projectedPossibleLives.find(({ possibleLife }) => (
    possibleLife.id === identity.id
    && possibleLife.work_subject_owner_id === identity.work_subject_owner_id
    && possibleLife.residence_property_id === identity.residence_property_id
    && possibleLife.living_time_residence_property_id
      === identity.living_time_residence_property_id
    && possibleLife.personal_meaning_reference === identity.personal_meaning_reference
  ));
  if (!projectedPossibleLife) return null;
  return {
    projectedPossibleLife,
    personalMeaning: focus.personal_meaning,
  };
}
