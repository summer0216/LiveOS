import { Suspense } from 'react';

import PropertyWorkspace from '@/features/property-workspace';

export default function PropertyWorkspacePage() {
  return (
    <Suspense fallback={null}>
      <PropertyWorkspace />
    </Suspense>
  );
}
