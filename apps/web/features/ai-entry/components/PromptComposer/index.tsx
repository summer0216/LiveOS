'use client';

import type { KeyboardEvent } from 'react';
import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';

interface PromptComposerProps {
  onListeningChange: (isListening: boolean) => void;
  onSubmitStart: () => void;
  onThinkingStart: () => void;
}

export default function PromptComposer({
  onListeningChange,
  onSubmitStart,
  onThinkingStart,
}: PromptComposerProps) {
  const router = useRouter();
  const [message, setMessage] = useState('');
  const [submitPhase, setSubmitPhase] = useState<'idle' | 'listening' | 'thinking'>(
    'idle',
  );
  const transitionTimers = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(() => {
    const timers = transitionTimers.current;

    return () => {
      timers.forEach(clearTimeout);
    };
  }, []);

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

    if (submitPhase !== 'idle') {
      return;
    }

    onSubmitStart();
    setSubmitPhase('listening');

    transitionTimers.current.push(
      setTimeout(() => {
        onThinkingStart();
        setSubmitPhase('thinking');
      }, 600),
      setTimeout(() => {
        router.push(`/conversation?${params.toString()}`);
      }, 1400),
    );
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
        disabled={submitPhase !== 'idle'}
        onChange={(event) => {
          const nextMessage = event.target.value;
          setMessage(nextMessage);
          onListeningChange(Boolean(nextMessage.trim()));
        }}
        onKeyDown={handleKeyDown}
        placeholder="Tell me about the life you're looking for..."
        className="w-full resize-none rounded-3xl border border-white/10 bg-[#10182b] px-6 py-5 text-white outline-none transition-[background-color,border-color,box-shadow] duration-200 placeholder:text-slate-600 hover:border-blue-400/50 hover:bg-[#121c31] focus:border-blue-500 focus:bg-[#10182b] focus:shadow-[0_0_0_6px_rgba(59,105,255,0.12)] disabled:cursor-not-allowed disabled:opacity-70"
      />

      <p className="mt-4 text-center text-sm text-neutral-500">
        {submitPhase === 'listening'
          ? '··· 正在聆听……'
          : submitPhase === 'thinking'
            ? '··· 正在开启对话……'
            : 'Press Enter to start · Shift + Enter for new line'}
      </p>
    </section>
  );
}
