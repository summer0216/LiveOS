import { Suspense } from 'react';

import LivingProfileWorkspace from '@/features/living-profile-workspace';

export default function LivingProfileWorkspacePage() {
  return (
    <Suspense fallback={null}>
      <LivingProfileWorkspace />
    </Suspense>
  );
}
