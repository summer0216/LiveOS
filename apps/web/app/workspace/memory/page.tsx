import { Suspense } from 'react';

import RouteLoading from '@/components/RouteLoading';
import MemoryWorkspace from '@/features/memory-workspace';

export default function MemoryWorkspacePage() {
  return (
    <Suspense fallback={<RouteLoading />}>
      <MemoryWorkspace />
    </Suspense>
  );
}
