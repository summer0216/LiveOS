'use client';

import type { GeographicProjection } from '@/features/living-map/AMapGround';
import { resolveWorldGeographicLod } from './geographicLod';
import styles from './PossibleLifeWorld.module.css';

interface RealityAnchorProjectionProps {
  identity: string | null;
  location: { lng: number; lat: number } | null;
  projection: GeographicProjection | null;
  zoom: number | null;
  visible: boolean;
}

export default function RealityAnchorProjection({
  identity,
  location,
  projection,
  zoom,
  visible,
}: RealityAnchorProjectionProps) {
  const projected = visible && identity && location && projection
    ? projection(location)
    : null;
  const position = projected
    ? { left: projected.x, top: projected.y }
    : null;

  if (!visible || !identity || !position) return null;
  const lod = resolveWorldGeographicLod(zoom);

  return (
    <div className={styles.anchorOverlay} aria-hidden="true">
      <div
        className={styles.realityAnchor}
        data-reality-anchor-lod={lod}
        data-reality-anchor="grounded-property"
        style={{ left: position.left, top: position.top }}
      >
        <span className={styles.anchorGlow} />
        <span className={styles.anchorRing} />
        <span className={styles.anchorCore} />
        <span className={styles.anchorLabel}>{identity}</span>
      </div>
    </div>
  );
}
