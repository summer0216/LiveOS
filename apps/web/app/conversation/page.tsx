import { Suspense } from 'react';

import RouteLoading from '@/components/RouteLoading';
import ConversationFeature from "@/features/conversation";

export default function ConversationPage() {
  return (
    <Suspense fallback={<RouteLoading />}>
      <ConversationFeature />
    </Suspense>
  );
}
