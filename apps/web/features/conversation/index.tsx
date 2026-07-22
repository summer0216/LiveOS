"use client";

import { useSearchParams } from "next/navigation";
import ConversationLayout from "./components/ConversationLayout";
import MessageBubble from "./components/MessageBubble";

export default function ConversationFeature() {
  const searchParams = useSearchParams();

  const message = searchParams.get("message") ?? "";

  return (
    <ConversationLayout>
      {message && (
        <MessageBubble
          role="user"
          content={message}
        />
      )}
    </ConversationLayout>
  );
}