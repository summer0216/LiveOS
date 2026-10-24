'use client';

import { CheckCircle2, ChevronRight, MapPin, ShoppingBag, TrainFront, X } from 'lucide-react';
import type { ProjectedEnvironment } from './selectEnvironmentProjection';
import styles from './environment-projection.module.css';

export function environmentDistance(item: ProjectedEnvironment) {
  return [item.distanceM === null ? null : `约 ${item.distanceM} 米`,
    item.walkingMinutes === null ? null : `步行约 ${item.walkingMinutes} 分钟`].filter(Boolean).join(' · ');
}

export default function EnvironmentDetail({ item, onClose }: {
  item: ProjectedEnvironment;
  onClose: () => void;
}) {
  const Icon = item.category === 'TRANSIT' ? TrainFront : item.category === 'COMMERCIAL' ? ShoppingBag : MapPin;
  const supplement = item.relevance === 'RELATED_RAIL_SUPPLEMENT';
  const source = /^https?:\/\//.test(item.evidence.source_reference) ? item.evidence.source_reference : null;
  return (
    <section className={styles.detail} role="region" data-category={item.category} aria-label={`${item.name}详情`}
      onKeyDown={(event) => { if (event.key === 'Escape') { event.stopPropagation(); onClose(); } }}>
      <div className={styles.handle} aria-hidden="true" />
      <button type="button" autoFocus className={styles.close} aria-label="关闭环境详情" onClick={onClose}><X size={20} /></button>
      <div className={styles.heading}>
        <span className={styles.icon}><Icon size={20} aria-hidden="true" /></span>
        <div><h2>{item.name}</h2><p>{environmentDistance(item)}</p></div>
      </div>
      <div className={styles.tags}>
        <span><CheckCircle2 size={14} aria-hidden="true" /> 已验证</span>
        <span>{item.typeCode === '150705' ? '有轨电车' : item.typeCode === '150500' ? '地铁' : '环境地点'}</span>
        <span>{supplement ? '相关轨道交通' : '当前关注'}</span>
      </div>
      <p className={styles.description}>{supplement ? '与你关注的轨道交通相关的有轨电车站点。' : '与你当前关注相关的真实环境地点。'}</p>
      <details className={styles.evidence}>
        <summary>查看证据详情 <ChevronRight size={18} aria-hidden="true" /></summary>
        <dl>
          <div><dt>来源</dt><dd>{source ? <a href={source} target="_blank" rel="noreferrer">{item.evidence.source_provider}</a> : item.evidence.source_provider}</dd></div>
          <div><dt>地点身份</dt><dd>{item.evidence.identity}</dd></div>
          <div><dt>来源记录</dt><dd>{item.evidence.source_record_id}</dd></div>
          <div><dt>获取时间</dt><dd><time dateTime={item.evidence.observed_at}>{new Date(item.evidence.observed_at).toLocaleString('zh-CN')}</time></dd></div>
        </dl>
      </details>
    </section>
  );
}
