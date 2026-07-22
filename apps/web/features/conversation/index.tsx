"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import ConversationLayout from "./components/ConversationLayout";
import MessageBubble from "./components/MessageBubble";

import { sendMessage } from "@/services/chat";

export default function ConversationFeature() {
  const searchParams = useSearchParams();

  const userMessage =
    searchParams.get("message") ?? "";

  const [reply, setReply] =
    useState("");

  useEffect(() => {
    if (!userMessage) return;

    sendMessage(userMessage)
      .then((res) => {
        setReply(res.reply);
      })
      .catch(console.error);

  }, [userMessage]);

  return (
    <ConversationLayout>

      <MessageBubble
        role="user"
        content={userMessage}
      />

      {reply && (
        <MessageBubble
          role="assistant"
          content={reply}
        />
      )}

    </ConversationLayout>
  );
}