'use client';

import { useEffect, useRef, useState } from 'react';

type AMapInstance = {
  destroy: () => void;
  lngLatToContainer: (location: AMapLngLat) => AMapPixel;
  getZoom: () => number;
  on: (
    event:
      | 'complete'
      | 'dragstart'
      | 'zoomstart'
      | 'zoomchange'
      | 'mapmove'
      | 'move'
      | 'moveend'
      | 'zoomend',
    handler: () => void,
  ) => void;
  resize: () => void;
  getFitZoomAndCenterByBounds: (
    bounds: AMapBounds,
    avoid: readonly [number, number, number, number],
    maxZoom?: number,
  ) => AMapFitResult;
  setZoomAndCenter: (zoom: number, center: AMapLngLat, immediately?: boolean) => void;
};

type AMapLngLat = {
  getLng: () => number;
  getLat: () => number;
};

type AMapPixel = {
  getX: () => number;
  getY: () => number;
};

type AMapBounds = {
  getSouthWest: () => AMapLngLat;
  getNorthEast: () => AMapLngLat;
};

type AMapFitResult = readonly [number, AMapLngLat];

type AMapConstructor = new (
  container: HTMLElement,
  options: Record<string, unknown>,
) => AMapInstance;

declare global {
  interface Window {
    AMap?: {
      Map: AMapConstructor;
      LngLat: new (lng: number, lat: number) => AMapLngLat;
      Bounds: new (southWest: AMapLngLat, northEast: AMapLngLat) => AMapBounds;
    };
    _AMapSecurityConfig?: { securityJsCode: string };
  }
}

export interface GeographicProjection {
  (location: { lng: number; lat: number }): { x: number; y: number };
}

interface AMapGroundProps {
  fitLocations?: readonly { lng: number; lat: number }[];
  onProjectionReady?: (projection: GeographicProjection) => void;
  onReturnToLivingWorldReady?: (action: (() => void) | null) => void;
  onUserExploredCameraChange?: (explored: boolean) => void;
  onZoomChange?: (zoom: number) => void;
}

const CAMERA_PADDING: readonly [number, number, number, number] = [
  96,
  220,
  300,
  280,
];

let amapLoadPromise: Promise<void> | null = null;

function loadAMap(key: string, securityJsCode: string) {
  if (window.AMap) return Promise.resolve();
  if (amapLoadPromise) return amapLoadPromise;

  window._AMapSecurityConfig = { securityJsCode };
  amapLoadPromise = new Promise<void>((resolve, reject) => {
    const script = document.createElement('script');
    script.src = `https://webapi.amap.com/maps?v=2.0&key=${encodeURIComponent(key)}`;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error('AMap Web JS API failed to load.'));
    document.head.appendChild(script);
  });

  return amapLoadPromise;
}

export default function AMapGround({
  fitLocations = [],
  onProjectionReady,
  onReturnToLivingWorldReady,
  onUserExploredCameraChange,
  onZoomChange,
}: AMapGroundProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const fitLocationsRef = useRef(fitLocations);
  const refitForLocationsChangeRef = useRef<(() => void) | null>(null);
  const [status, setStatus] = useState<'loading' | 'ready' | 'missing-config' | 'error'>(
    'loading',
  );

  useEffect(() => {
    fitLocationsRef.current = fitLocations;
    refitForLocationsChangeRef.current?.();
  }, [fitLocations]);

  useEffect(() => {
    const key = process.env.NEXT_PUBLIC_AMAP_KEY;
    const securityJsCode = process.env.NEXT_PUBLIC_AMAP_SECURITY_CODE;

    if (!key || !securityJsCode) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setStatus('missing-config');
      return;
    }

    let active = true;
    let map: AMapInstance | null = null;
    let refitOnResize: (() => void) | null = null;
    let resizeObserver: ResizeObserver | null = null;
    let userExploredCamera = false;
    let programmaticCameraUpdateUntil = 0;

    void loadAMap(key, securityJsCode)
      .then(() => {
        if (!active || !containerRef.current || !window.AMap) return;

        const mapInstance = new window.AMap.Map(containerRef.current, {
          center: [113.9345, 22.5329],
          zoom: 13,
          viewMode: '2D',
          mapStyle: 'amap://styles/fresh',
          features: ['bg', 'road'],
          showLabel: true,
          dragEnable: true,
          zoomEnable: true,
          doubleClickZoom: true,
          keyboardEnable: false,
          jogEnable: false,
          animateEnable: false,
        });
        map = mapInstance;

        const createProjection = (): GeographicProjection => ({ lng, lat }) => {
          const pixel = mapInstance.lngLatToContainer(
            new window.AMap!.LngLat(lng, lat),
          );
          return {
            x: pixel.getX(),
            y: pixel.getY(),
          };
        };

        const refreshProjection = () => {
          if (!active) return;
          onProjectionReady?.(createProjection());
        };

        const refreshZoom = () => {
          if (!active) return;
          onZoomChange?.(mapInstance.getZoom());
        };

        const fitGroundedLocations = (smooth = false) => {
          const currentFitLocations = fitLocationsRef.current;
          if (currentFitLocations.length < 2 || !window.AMap) return;

          const longitudes = currentFitLocations.map(({ lng }) => lng);
          const latitudes = currentFitLocations.map(({ lat }) => lat);
          const bounds = new window.AMap.Bounds(
            new window.AMap.LngLat(Math.min(...longitudes), Math.min(...latitudes)),
            new window.AMap.LngLat(Math.max(...longitudes), Math.max(...latitudes)),
          );
          const fit = mapInstance.getFitZoomAndCenterByBounds(
            bounds,
            CAMERA_PADDING,
            16,
          );
          programmaticCameraUpdateUntil = performance.now() + (smooth ? 1500 : 250);
          mapInstance.setZoomAndCenter(fit[0], fit[1], !smooth);
          refreshProjection();
          refreshZoom();
        };

        const returnToLivingWorld = () => {
          userExploredCamera = false;
          onUserExploredCameraChange?.(false);
          fitGroundedLocations(true);
        };
        onReturnToLivingWorldReady?.(returnToLivingWorld);
        refitForLocationsChangeRef.current = () => {
          refreshProjection();
          if (!userExploredCamera) fitGroundedLocations();
        };

        let hasFittedInitialView = false;
        const markUserExploredCamera = () => {
          if (performance.now() < programmaticCameraUpdateUntil) return;
          userExploredCamera = true;
          onUserExploredCameraChange?.(true);
        };
        mapInstance.on('dragstart', markUserExploredCamera);
        mapInstance.on('zoomstart', markUserExploredCamera);
        mapInstance.on('zoomchange', () => {
          refreshProjection();
          refreshZoom();
        });
        mapInstance.on('mapmove', refreshProjection);
        mapInstance.on('move', refreshProjection);
        mapInstance.on('moveend', refreshProjection);
        mapInstance.on('zoomend', refreshProjection);
        mapInstance.on('complete', () => {
          if (!active) return;

          if (!hasFittedInitialView) {
            hasFittedInitialView = true;
            fitGroundedLocations();
            setStatus('ready');
            return;
          }
          refreshProjection();
        });

        refitOnResize = () => {
          if (!active || userExploredCamera) return;
          mapInstance.resize();
          fitGroundedLocations();
        };
        window.addEventListener('resize', refitOnResize);
        resizeObserver = new ResizeObserver(refitOnResize);
        resizeObserver.observe(containerRef.current);
      })
      .catch((error: unknown) => {
        console.error('Failed to initialize AMap ground:', error);
        if (active) setStatus('error');
      });

    return () => {
      active = false;
      if (refitOnResize) window.removeEventListener('resize', refitOnResize);
      resizeObserver?.disconnect();
      refitForLocationsChangeRef.current = null;
      onReturnToLivingWorldReady?.(null);
      map?.destroy();
    };
  }, [
    onProjectionReady,
    onReturnToLivingWorldReady,
    onUserExploredCameraChange,
    onZoomChange,
  ]);

  return (
    <div
      aria-hidden="true"
      data-map-status={status}
      className="absolute inset-0 z-0 overflow-hidden bg-[#eef2ed]"
    >
      <div className={`map-reveal-layer absolute inset-0${status === 'ready' ? ' is-ready' : ''}`}>
        <div ref={containerRef} className="h-full w-full" />
      </div>
    </div>
  );
}
