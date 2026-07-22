"use client";

import { useState, KeyboardEvent } from "react";
import { useRouter } from "next/navigation";

export default function PromptComposer() {
  const router = useRouter();

  const [message, setMessage] = useState("");

  const submit = () => {
    const value = message.trim();

    if (!value) return;

    router.push(
      `/conversation?message=${encodeURIComponent(value)}`
    );
  };

  const handleKeyDown = (
    event: KeyboardEvent<HTMLTextAreaElement>
  ) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  };

  return (
    <section className="mt-12 w-full max-w-2xl">

      <textarea
        rows={3}
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Tell me about the life you're looking for..."
        className="
          w-full
          resize-none
          rounded-3xl
          border
          border-white/10
          bg-white/5
          px-6
          py-5
          text-white
          outline-none
          transition
          placeholder:text-neutral-500
          focus:border-white/30
          focus:bg-white/10
        "
      />

      <p className="mt-4 text-center text-sm text-neutral-500">
        Press Enter to start · Shift + Enter for new line
      </p>

    </section>
  );
}