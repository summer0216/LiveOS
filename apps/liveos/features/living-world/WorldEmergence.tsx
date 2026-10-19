'use client';

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { LocateFixed, Minus, Plus } from 'lucide-react';
import AMapGround from '@/features/living-map/AMapGround';
import type { GeographicCameraReorient, GeographicProjection } from '@/lib/runtimePresentationContract';
import type { GroundedPlace } from './groundedPlace';
import styles from './world-emergence.module.css';

export default function WorldEmergence({ place, animateAppearance = false }: { place: GroundedPlace; animateAppearance?: boolean }) {
  const anchor = useRef<HTMLSpanElement>(null);
  const currentPlace = useRef(place);
  const animate = useRef(animateAppearance);
  const camera = useRef<GeographicCameraReorient | null>(null);
  const projection = useRef<GeographicProjection | null>(null);
  const groundReady = useRef(false);
  const [ready, setReady] = useState(false);
  const zoom = useRef<number | null>(null);
  useLayoutEffect(() => {
    currentPlace.current = place;
    animate.current = animateAppearance;
  }, [place, animateAppearance]);
  const updateAnchor = useCallback((project: GeographicProjection) => {
    projection.current = project;
    if (!anchor.current || !groundReady.current) return;
    const point = project(currentPlace.current.center);
    anchor.current.style.left = `${point.x}px`;
    anchor.current.style.top = `${point.y}px`;
    anchor.current.style.visibility = 'visible';
    if (!anchor.current.dataset.positioned) {
      anchor.current.dataset.reveal = String(animate.current);
      anchor.current.dataset.positioned = 'true';
    }
  }, []);
  const receiveCamera = useCallback((reorient: GeographicCameraReorient) => { camera.current = reorient; }, []);
  const receiveZoom = useCallback((value: number) => { zoom.current = value; }, []);
  const receiveGroundReady = useCallback((value: boolean) => {
    groundReady.current = value;
    setReady(value);
    if (value && projection.current) updateAnchor(projection.current);
  }, [updateAnchor]);
  useEffect(() => {
    // A newly admitted focus uses the same instance and authoritative framing.
    const current = currentPlace.current;
    if (groundReady.current) camera.current?.(current.center, current.framing);
  }, [place.identity, place.center.lng, place.center.lat, place.framing.level, place.framing.attention]);
  const changeZoom = (step: number) => {
    if (zoom.current !== null) camera.current?.(place.center, zoom.current + step, null, anchor.current);
  };
  return (
    <section className={styles.world} aria-label={`以${place.identity}为中心的生活世界`}>
      <AMapGround
        initialCenter={place.center}
        initialFraming={place.framing}
        onProjectionReady={updateAnchor}
        onCameraReady={receiveCamera}
        onGroundReadyChange={receiveGroundReady}
        onZoomChange={receiveZoom}
      />
      <span
        ref={anchor}
        key={`${place.identity}:${place.center.lng}:${place.center.lat}`}
        className={styles.anchor}
        role="img"
        aria-label={`${place.name || place.identity}的位置`}
      >
        <svg className={styles.pin} viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 1C6.48 1 2 5.48 2 11c0 5 10 12 10 12s10-7 10-12C22 5.48 17.52 1 12 1Z" />
          <circle cx="12" cy="10" r="4" />
        </svg>
        {place.name && <span className={styles.label} data-place-label title={place.name}>{place.name}</span>}
      </span>
      <div className={styles.controls} role="group" aria-label="地图控件">
        <div className={styles.zoomControls}>
          <button type="button" aria-label="放大地图" disabled={!ready} onClick={() => changeZoom(1)}><Plus size={20} /></button>
          <button type="button" aria-label="缩小地图" disabled={!ready} onClick={() => changeZoom(-1)}><Minus size={20} /></button>
        </div>
        <button type="button" aria-label="返回当前地点" disabled={!ready} onClick={() => camera.current?.(place.center, place.framing)}><LocateFixed size={20} /></button>
      </div>
    </section>
  );
}
