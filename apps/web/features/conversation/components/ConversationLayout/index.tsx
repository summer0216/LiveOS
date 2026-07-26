import { ReactNode } from "react";

interface Props {
  children: ReactNode;
}

export default function ConversationLayout({
  children,
}: Props) {
  return (
    <main className="h-screen overflow-hidden bg-black text-white">
      <div className="mx-auto flex h-full w-full max-w-4xl flex-col px-6 py-10">
        {children}
      </div>
    </main>
  );
}