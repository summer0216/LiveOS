'use client';

import { useState } from 'react';

import AICore, {
  type AICoreState,
} from '@/features/ai-entry/components/AICore';
import Welcome from "@/features/ai-entry/components/welcome";
import PromptComposer from "@/features/ai-entry/components/PromptComposer";

export default function HomePage() {
  const [coreState, setCoreState] = useState<AICoreState>('idle');

  return (
    <main className="min-h-screen bg-black text-white">
      <div className="mx-auto flex min-h-screen max-w-3xl flex-col items-center justify-center px-6">

        <AICore state={coreState} />

        <Welcome />

        <PromptComposer
          onListeningChange={(isListening) => {
            setCoreState(isListening ? 'listening' : 'idle');
          }}
          onSubmitStart={() => {
            setCoreState('listening');
          }}
          onThinkingStart={() => {
            setCoreState('thinking');
          }}
        />

      </div>
    </main>
  );
}
