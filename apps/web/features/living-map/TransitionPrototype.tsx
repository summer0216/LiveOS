'use client';

import { useCallback, useState } from 'react';

import ConversationComposer from '@/features/conversation/components/ConversationComposer';
import AMapGround from '@/features/living-map/AMapGround';

const CHENGDU = { lng: 104.0668, lat: 30.5728 } as const;
const SHENZHEN = { lng: 114.0579, lat: 22.5431 } as const;

export default function TransitionPrototype() {
  const [reorient, setReorient] = useState<
    ((center: { lng: number; lat: number }, zoom: number) => void) | null
  >(null);
  const [submitted, setSubmitted] = useState(false);

  const handleCameraReady = useCallback(
    (nextReorient: (center: { lng: number; lat: number }, zoom: number) => void) => {
      setReorient(() => nextReorient);
    },
    [],
  );

  const handleSubmit = useCallback((message: string) => {
    if (!message.trim() || !reorient) return;
    setSubmitted(true);
    reorient(SHENZHEN, 11.5);
  }, [reorient]);

  return (
    <main className="relative min-h-screen overflow-hidden bg-[#eef2ed] text-slate-950">
      <AMapGround
        initialCenter={CHENGDU}
        initialZoom={10.5}
        presentation="quiet"
        onCameraReady={handleCameraReady}
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 z-[1] bg-[radial-gradient(ellipse_at_center,rgba(238,242,237,0.66)_0%,rgba(238,242,237,0.42)_36%,rgba(238,242,237,0.12)_72%,transparent_100%)]"
      />
      <section
        aria-label="Decision Geography transition prototype"
        className="relative z-10 min-h-screen"
        data-transition-state={submitted ? 'shenzhen' : 'chengdu'}
      >
        <h1
          className={`pointer-events-none absolute inset-x-0 top-1/2 -translate-y-1/2 text-center text-[clamp(2rem,4vw,3.5rem)] font-normal leading-[1.15] tracking-[-0.03em] text-slate-900 transition-opacity duration-700 ${submitted ? 'opacity-0' : 'opacity-100'}`}
        >
          你的生活，
          <br />
          从哪里开始？
        </h1>
      </section>
      <div className="absolute inset-x-0 bottom-0 z-20 px-5 pb-5 sm:px-10 sm:pb-8">
        <div className="mx-auto max-w-3xl">
          <ConversationComposer
            variant="ambient"
            placeholder="告诉 LiveOS，你现在最想解决的生活问题……"
            onSubmit={handleSubmit}
            onListeningChange={() => undefined}
          />
        </div>
      </div>
    </main>
  );
}
