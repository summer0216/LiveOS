import { Suspense } from 'react';

import RouteLoading from '@/components/RouteLoading';
import PropertyWorkspace from '@/features/property-workspace';

export default function PropertyWorkspacePage() {
  return (
    <Suspense fallback={<RouteLoading />}>
      <PropertyWorkspace />
    </Suspense>
  );
}
