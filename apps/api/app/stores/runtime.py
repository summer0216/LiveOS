from app.core.config import settings
from app.stores.database import Database
from app.stores.persistent import (
    ConversationStore,
    DecisionActionStateStore,
    DecisionGeographyStore,
    DecisionRecordStore,
    DecisionUnknownStore,
    LatestVerifiedActionStore,
    LivingTimeRelationshipStore,
    PossibleLifeMeaningfulUnknownStore,
    PossibleLifePersonalMeaningStore,
    PossibleLifeRealityActionStore,
    PossibleLifeStore,
    ProfileStore,
    PropertyStore,
    RealityNeedStore,
    WorkSubjectStore,
)

database = Database(settings.DATABASE_URL)
database.initialize()
conversation_store = ConversationStore(database)
decision_geography_store = DecisionGeographyStore(database)
profile_store = ProfileStore(database)
work_subject_store = WorkSubjectStore(database)
living_time_relationship_store = LivingTimeRelationshipStore(database)
possible_life_store = PossibleLifeStore(database)
possible_life_personal_meaning_store = PossibleLifePersonalMeaningStore(database)
possible_life_meaningful_unknown_store = PossibleLifeMeaningfulUnknownStore(database)
reality_need_store = RealityNeedStore(database)
possible_life_reality_action_store = PossibleLifeRealityActionStore(database)
property_store = PropertyStore(database)
decision_unknown_store = DecisionUnknownStore(database)
decision_record_store = DecisionRecordStore(database)
decision_action_state_store = DecisionActionStateStore(database)
latest_verified_action_store = LatestVerifiedActionStore(database)
DEFAULT_ANONYMOUS_USER_ID = "00000000-0000-0000-0000-000000000001"
conversation_store.ensure_user(DEFAULT_ANONYMOUS_USER_ID)
