from app.core.config import settings
from app.stores.database import Database
from app.stores.persistent import (
    ConversationStore,
    DecisionActionStateStore,
    DecisionRecordStore,
    LatestVerifiedActionStore,
    ProfileStore,
    PropertyStore,
)

database = Database(settings.DATABASE_URL)
database.initialize()
conversation_store = ConversationStore(database)
profile_store = ProfileStore(database)
property_store = PropertyStore(database)
decision_record_store = DecisionRecordStore(database)
decision_action_state_store = DecisionActionStateStore(database)
latest_verified_action_store = LatestVerifiedActionStore(database)
DEFAULT_ANONYMOUS_USER_ID = "00000000-0000-0000-0000-000000000001"
conversation_store.ensure_user(DEFAULT_ANONYMOUS_USER_ID)
