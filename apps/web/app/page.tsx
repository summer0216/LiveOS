import AIOrb from "@/features/ai-entry/components/AIOrb";
import Welcome from "@/features/ai-entry/components/Welcome";
import PromptComposer from "@/features/ai-entry/components/PromptComposer";

export default function HomePage() {
  return (
    <main className="min-h-screen bg-black text-white">
      <div className="mx-auto flex min-h-screen max-w-3xl flex-col items-center justify-center px-6">

        <AIOrb />

        <Welcome />

        <PromptComposer />

      </div>
    </main>
  );
}