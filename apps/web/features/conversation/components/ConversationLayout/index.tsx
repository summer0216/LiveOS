import { ReactNode } from "react";

interface Props {
  children: ReactNode;
}

export default function ConversationLayout({
  children,
}: Props) {
  return (
    <main className="min-h-screen bg-black text-white">
      <div className="mx-auto flex min-h-screen w-full max-w-4xl flex-col px-6 py-10">
        {children}
      </div>
    </main>
  );
}