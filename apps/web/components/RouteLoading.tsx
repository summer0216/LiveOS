export default function RouteLoading() {
  return (
    <main
      role="status"
      aria-label="页面加载中"
      className="flex min-h-screen items-center justify-center bg-[#050812] text-slate-500"
    >
      <div className="flex flex-col items-center gap-4">
        <span className="h-10 w-10 animate-pulse rounded-full bg-[radial-gradient(circle_at_35%_30%,#8d78ff_0,#5265dd_48%,#1a275a_100%)] shadow-[0_0_28px_rgba(93,91,255,0.3)]" />
        <span className="font-mono text-xs tracking-[0.16em]">
          LOADING
        </span>
      </div>
    </main>
  );
}
