import { Suspense } from 'react';

import RouteLoading from '@/components/RouteLoading';
import LivingProfileWorkspace from '@/features/living-profile-workspace';

export default function LivingProfileWorkspacePage() {
  return (
    <Suspense fallback={<RouteLoading />}>
      <LivingProfileWorkspace />
    </Suspense>
  );
}
