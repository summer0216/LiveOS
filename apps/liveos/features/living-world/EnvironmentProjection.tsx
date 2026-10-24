'use client';

import { useCallback, useLayoutEffect, useRef, useState } from 'react';
import { MapPin, ShoppingBag, TrainFront } from 'lucide-react';
import type { GeographicProjection } from '@/lib/runtimePresentationContract';
import type { ProjectedEnvironment } from './selectEnvironmentProjection';
import EnvironmentDetail, { environmentDistance } from './EnvironmentDetail';
import styles from './environment-projection.module.css';

export type ProjectionListener = (project: GeographicProjection) => void;

export default function EnvironmentProjection({ items, ready, onProjectionListener }: {
  items: readonly ProjectedEnvironment[];
  ready: boolean;
  onProjectionListener: (listener: ProjectionListener | null) => void;
}) {
  const anchors = useRef(new Map<string, HTMLButtonElement>());
  const currentItems = useRef(items);
  const projection = useRef<GeographicProjection | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = items.find((item) => item.id === selectedId);
  const update = useCallback((project: GeographicProjection) => {
    projection.current = project;
    for (const item of currentItems.current) {
      const node = anchors.current.get(item.id);
      if (!node) continue;
      const point = project(item.center);
      node.style.left = `${point.x}px`;
      node.style.top = `${point.y}px`;
      node.style.visibility = 'visible';
    }
  }, []);
  useLayoutEffect(() => {
    currentItems.current = items;
    if (ready && projection.current) update(projection.current);
  }, [items, ready, update]);
  useLayoutEffect(() => {
    onProjectionListener(update);
    return () => onProjectionListener(null);
  }, [onProjectionListener, update]);
  const close = () => {
    setSelectedId(null);
    if (selectedId) anchors.current.get(selectedId)?.focus();
  };
  return (
    <div className={styles.layer} hidden={!ready} aria-label="当前关注的环境">
      {items.map((item) => {
        const Icon = item.category === 'TRANSIT' ? TrainFront : item.category === 'COMMERCIAL' ? ShoppingBag : MapPin;
        return <button key={item.id} type="button" className={styles.marker}
          ref={(node) => { if (node) anchors.current.set(item.id, node); else anchors.current.delete(item.id); }}
          data-category={item.category} data-relevance={item.relevance} data-environment-id={item.id}
          aria-label={`${item.name}，${item.relevance === 'RELATED_RAIL_SUPPLEMENT' ? '相关轨道交通' : '当前关注'}，查看详情`}
          aria-expanded={selectedId === item.id} onClick={() => setSelectedId(item.id)}>
          <span className={styles.icon}><Icon size={20} aria-hidden="true" /></span>
          <span className={styles.markerText}><strong>{item.name}</strong><small>{environmentDistance(item)}</small></span>
        </button>;
      })}
      {selected && <EnvironmentDetail item={selected} onClose={close} />}
    </div>
  );
}
