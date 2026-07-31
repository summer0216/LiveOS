import { Suspense } from 'react';

import RouteLoading from '@/components/RouteLoading';
import ProfileFeature from '@/features/profile';

export default function ProfilePage() {
    return (
        <Suspense fallback={<RouteLoading />}>
            <ProfileFeature />
        </Suspense>
    );
}
