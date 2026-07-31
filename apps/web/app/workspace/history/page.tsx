import { Suspense } from 'react';

import RouteLoading from '@/components/RouteLoading';
import HistoryWorkspace from '@/features/history-workspace';

export default function HistoryWorkspacePage() {
  return (
    <Suspense fallback={<RouteLoading />}>
      <HistoryWorkspace />
    </Suspense>
  );
}
