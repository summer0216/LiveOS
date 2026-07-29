import { Suspense } from 'react';

import ConversationFeature from "@/features/conversation";

export default function ConversationPage() {
  return (
    <Suspense fallback={null}>
      <ConversationFeature />
    </Suspense>
  );
}
