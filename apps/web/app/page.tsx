export default function HomePage() {
  return (
    <main className="min-h-screen bg-black text-white">
      <div className="mx-auto flex min-h-screen w-full max-w-3xl flex-col items-center justify-center px-6">
        {/* AI Core */}
        <AIOrb />

        {/* Welcome */}
        <div id="welcome" />

        {/* Prompt */}
        <PromptInput />
      </div>
    </main>
  );
}