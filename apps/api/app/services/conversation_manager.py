from app.models.conversation import Conversation, ConversationMessage


class ConversationManager:
    def __init__(self) -> None:
        self._conversations: dict[str, Conversation] = {}

    def get_or_create(
        self,
        conversation_id: str,
    ) -> Conversation:
        conversation = self._conversations.get(conversation_id)

        if conversation is None:
            conversation = Conversation(
                conversation_id=conversation_id,
            )
            self._conversations[conversation_id] = conversation
        return conversation

    def get(
        self,
        conversation_id: str,
    ) -> Conversation | None:
        return self._conversations.get(conversation_id)

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

        if conversation_id not in self._conversations:
            return False

        del self._conversations[conversation_id]
        return True


conversation_manager = ConversationManager()
