'use client';

import type { KeyboardEvent } from 'react';
import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function PromptComposer() {
  const router = useRouter();
  const [message, setMessage] = useState('');

  const submit = () => {
    const value = message.trim();

    if (!value) {
      return;
    }

    const conversationId = crypto.randomUUID();
    const params = new URLSearchParams({
      conversation_id: conversationId,
      message: value,
    });

    router.push(`/conversation?${params.toString()}`);
  };

  const handleKeyDown = (
    event: KeyboardEvent<HTMLTextAreaElement>,
  ) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  };

  return (
    <section className="mt-12 w-full max-w-2xl">
      <textarea
        rows={3}
        value={message}
        onChange={(event) => setMessage(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Tell me about the life you're looking for..."
        className="w-full resize-none rounded-3xl border border-white/10 bg-white/5 px-6 py-5 text-white outline-none transition placeholder:text-neutral-500 focus:border-white/30 focus:bg-white/10"
      />

      <p className="mt-4 text-center text-sm text-neutral-500">
        Press Enter to start · Shift + Enter for new line
      </p>
    </section>
  );
}