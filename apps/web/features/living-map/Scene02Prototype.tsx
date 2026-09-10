'use client';

import ConversationComposer from '@/features/conversation/components/ConversationComposer';
import AMapGround from '@/features/living-map/AMapGround';

const NANSHAN_WORK = { lng: 113.9307, lat: 22.5333 } as const;

export default function Scene02Prototype() {
  return (
    <main
      className="relative min-h-screen overflow-hidden bg-[#eef2ed] text-slate-950"
      data-prototype="d2.1-scene-02"
    >
      <style>{'nextjs-portal { display: none !important; }'}</style>

      <div className="absolute inset-0 [&>div]:pointer-events-none">
        <AMapGround
          initialCenter={NANSHAN_WORK}
          initialZoom={12.6}
          presentation="quiet"
        />
      </div>

      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 bottom-0 z-[1] h-[32vh] bg-gradient-to-b from-transparent via-[#eef2ed]/35 to-[#eef2ed]/80"
      />

      <section
        aria-label="First Living Reality"
        className="relative z-10 min-h-screen"
      >
        <div className="absolute left-1/2 top-[45%] -translate-x-1/2 -translate-y-1/2">
          <div
            className="relative isolate flex items-start gap-4 text-left text-[#173d35] [filter:drop-shadow(0_1px_2px_rgba(255,255,255,0.98))]"
            aria-label="我的工作，南山"
          >
            <span
              aria-hidden="true"
              className="absolute -inset-x-7 -inset-y-5 -z-10 bg-[radial-gradient(ellipse_at_center,rgba(238,242,237,0.94)_0%,rgba(238,242,237,0.72)_42%,rgba(238,242,237,0)_74%)] blur-[1px]"
            />
            <span
              aria-hidden="true"
              className="mt-[-0.3rem] font-serif text-[3.25rem] font-normal leading-none tracking-[-0.1em]"
            >
              ◎
            </span>
            <span className="flex flex-col">
              <span className="font-mono text-[0.76rem] font-semibold leading-4 tracking-[0.17em] text-[#315b52]">
                我的工作
              </span>
              <span className="mt-1.5 text-[1.6rem] font-semibold leading-7 tracking-[0.025em] text-[#102f29]">
                南山
              </span>
            </span>
          </div>
        </div>
      </section>

      <div className="absolute inset-x-0 bottom-0 z-20 px-5 pb-5 sm:px-10 sm:pb-8">
        <div className="mx-auto max-w-[32rem] opacity-70 transition-opacity duration-200 focus-within:opacity-100">
          <ConversationComposer
            variant="ambient"
            placeholder="告诉 LiveOS 新情况……"
            onSubmit={() => undefined}
            onListeningChange={() => undefined}
          />
        </div>
      </div>
    </main>
  );
}
