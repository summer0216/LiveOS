'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

import RouteLoading from '@/components/RouteLoading';
import AICore, {
  type AICoreState,
} from '@/features/ai-entry/components/AICore';
import Welcome from "@/features/ai-entry/components/welcome";
import PromptComposer from "@/features/ai-entry/components/PromptComposer";
import { getLivingDecisionResume } from '@/services/resume';

export default function HomePage() {
  const router = useRouter();
  const [coreState, setCoreState] = useState<AICoreState>('idle');
  const [isResolvingResume, setIsResolvingResume] = useState(true);

  useEffect(() => {
    let active = true;

    async function resolveResume() {
      try {
        const state = await getLivingDecisionResume();
        if (!active) return;
        if (state.conversation_id) {
          router.replace(
            `/conversation?conversation_id=${encodeURIComponent(state.conversation_id)}`,
          );
          return;
        }
      } catch (error: unknown) {
        console.error('Failed to resolve living decision resume:', error);
      }
      if (active) setIsResolvingResume(false);
    }

    void resolveResume();
    return () => {
      active = false;
    };
  }, [router]);

  if (isResolvingResume) {
    return <RouteLoading />;
  }

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
