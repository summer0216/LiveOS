'use client';

import ConversationComposer from '@/features/conversation/components/ConversationComposer';
import AMapGround from '@/features/living-map/AMapGround';

export default function HomePage() {
  return (
    <main className="relative min-h-screen overflow-hidden bg-[#eef2ed] text-slate-950">
      <AMapGround
        initialCenter={{ lng: 113.93, lat: 22.54 }}
        initialZoom={12.5}
        presentation="quiet"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 z-[1] bg-[radial-gradient(ellipse_at_center,rgba(238,242,237,0.78)_0%,rgba(238,242,237,0.62)_30%,rgba(238,242,237,0.35)_58%,rgba(238,242,237,0.12)_80%,transparent_100%)]"
      />
      <section
        aria-label="Empty Living World"
        className="relative z-10 flex min-h-screen flex-col items-center justify-center px-6 pb-36 text-center"
      >
        <h1 className="max-w-xl text-[clamp(1.85rem,4vw,3.4rem)] font-normal leading-[1.15] tracking-[-0.025em] text-slate-900/90">
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
            onSubmit={() => undefined}
            onListeningChange={() => undefined}
          />
        </div>
      </div>
    </main>
  );
}
