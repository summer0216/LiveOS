'use client';

import { useEffect, type RefObject } from 'react';

/** Keep the sheet above the keyboard without resizing the underlying map. */
export function useVisibleViewport(surface: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const viewport = window.visualViewport;
    if (!viewport) return;
    const update = () => {
      surface.current?.style.setProperty('--world-visible-height', `${viewport.height}px`);
      surface.current?.style.setProperty('--world-keyboard-inset', `${Math.max(0, window.innerHeight - viewport.height - viewport.offsetTop)}px`);
    };
    update();
    viewport.addEventListener('resize', update);
    viewport.addEventListener('scroll', update);
    return () => {
      viewport.removeEventListener('resize', update);
      viewport.removeEventListener('scroll', update);
    };
  }, [surface]);
}
