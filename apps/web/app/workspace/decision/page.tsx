import { Suspense } from 'react';

import DecisionWorkspace from '@/features/decision-workspace';

export default function DecisionWorkspacePage() {
  return (
    <Suspense fallback={null}>
      <DecisionWorkspace />
    </Suspense>
  );
}
