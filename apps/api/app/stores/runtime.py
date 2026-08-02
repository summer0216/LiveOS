from app.core.config import settings
from app.stores.database import Database
from app.stores.persistent import (
    ConversationStore,
    DecisionRecordStore,
    ProfileStore,
    PropertyStore,
)

database = Database(settings.DATABASE_PATH)
database.initialize()
conversation_store = ConversationStore(database)
profile_store = ProfileStore(database)
property_store = PropertyStore(database)
decision_record_store = DecisionRecordStore(database)
DEFAULT_ANONYMOUS_USER_ID = "system-test-owner"
conversation_store.ensure_user(DEFAULT_ANONYMOUS_USER_ID)
