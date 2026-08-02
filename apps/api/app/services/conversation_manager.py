from app.models.conversation import Conversation, ConversationMessage
from app.stores.runtime import DEFAULT_ANONYMOUS_USER_ID, conversation_store


class ConversationManager:
    def get_or_create(
        self,
        conversation_id: str,
        user_id: str = DEFAULT_ANONYMOUS_USER_ID,
    ) -> Conversation:
        return conversation_store.get_or_create(conversation_id, user_id)

    def get(
        self,
        conversation_id: str,
    ) -> Conversation | None:
        return conversation_store.get(conversation_id)

    def get_history(
        self,
        conversation_id: str,
    ) -> list[ConversationMessage]:
        conversation = self.get(conversation_id)

        if conversation is None:
            return []

        return conversation.get_messages()

    def delete(
        self,
        conversation_id: str,
    ) -> bool:
        return conversation_store.delete(conversation_id)

    def belongs_to(self, conversation_id: str, user_id: str) -> bool:
        return conversation_store.belongs_to(conversation_id, user_id)

    def append_user_message(self, conversation_id: str, content: str) -> None:
        conversation_store.append(conversation_id, "user", content)

    def append_assistant_message(self, conversation_id: str, content: str) -> None:
        conversation_store.append(conversation_id, "assistant", content)


conversation_manager = ConversationManager()
