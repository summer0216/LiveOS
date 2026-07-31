import { Suspense } from 'react';

import RouteLoading from '@/components/RouteLoading';
import DecisionWorkspace from '@/features/decision-workspace';

export default function DecisionWorkspacePage() {
  return (
    <Suspense fallback={<RouteLoading />}>
      <DecisionWorkspace />
    </Suspense>
  );
}
