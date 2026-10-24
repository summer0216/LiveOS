'use client';

import { useEffect, useState } from 'react';
import { getProperties, type Property } from '../../infrastructure/groundedRealityApi';
import { selectGroundedPlace, type GroundedPlace } from './groundedPlace';

export function useGroundedPlace(conversationId: string, refreshKey: number) {
  const [reality, setReality] = useState<{
    conversationId: string;
    place: GroundedPlace | null;
    properties: Property[];
    error: string | null;
  } | null>(null);

  useEffect(() => {
    if (!conversationId) {
      return;
    }
    const controller = new AbortController();
    getProperties(conversationId, controller.signal)
      .then((properties) => {
        if (!controller.signal.aborted) {
          setReality({ conversationId, place: selectGroundedPlace(conversationId, properties), properties, error: null });
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setReality({ conversationId, place: null, properties: [], error: '无法恢复地点，请刷新重试。' });
          console.error('Unable to restore grounded place reality.', error);
        }
      });
    return () => controller.abort();
  }, [conversationId, refreshKey]);

  const resolved = reality?.conversationId === conversationId;
  return {
    place: resolved ? reality.place : null,
    properties: resolved ? reality.properties : [],
    isRestoring: Boolean(conversationId) && !resolved,
    error: resolved ? reality.error : null,
  };
}
