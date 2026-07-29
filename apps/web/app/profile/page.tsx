import { Suspense } from 'react';

import ProfileFeature from '@/features/profile';

export default function ProfilePage() {
    return (
        <Suspense fallback={null}>
            <ProfileFeature />
        </Suspense>
    );
}
