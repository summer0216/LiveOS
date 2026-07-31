import AICore from '@/features/ai-entry/components/AICore';

export default function RouteLoading() {
  return (
    <main
      role="status"
      aria-label="页面加载中"
      className="flex min-h-screen items-center justify-center bg-[#050812] text-slate-500"
    >
      <div className="flex flex-col items-center gap-4">
        <AICore state="thinking" size="runtime" />
        <span className="font-mono text-xs tracking-[0.16em]">
          LOADING
        </span>
      </div>
    </main>
  );
}
