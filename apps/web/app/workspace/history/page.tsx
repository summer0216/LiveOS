import { Suspense } from 'react';

import HistoryWorkspace from '@/features/history-workspace';

export default function HistoryWorkspacePage() {
  return (
    <Suspense fallback={null}>
      <HistoryWorkspace />
    </Suspense>
  );
}
