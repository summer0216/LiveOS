from app.models.conversation import ConversationMessage
from app.models.profile_patch import LivingProfilePatch


class ProfileIntelligence:
    def extract(
        self,
        history: list[ConversationMessage],
    ) -> LivingProfilePatch:
        """
        根据 Conversation History
        提取 LivingProfilePatch。

        Sprint 6 第一版暂时返回空 Patch。
        """

        _ = history

        return LivingProfilePatch()


profile_intelligence = ProfileIntelligence()
