'use client';

import { useLayoutEffect, useRef, useState } from 'react';
import { rentBudgetMeaning } from '@/lib/rentBudgetMeaning';

type Point = { x: number; y: number };
type Size = { width: number; height: number };
type Box = Point & Size;

function intersects(a: Box, b: Box) {
  return a.x < b.x + b.width + 8 && a.x + a.width + 8 > b.x
    && a.y < b.y + b.height + 8 && a.y + a.height + 8 > b.y;
}

function positions(anchor: Point, size: Size): Box[] {
  return [
    { x: anchor.x + 24, y: anchor.y - size.height / 2, ...size },
    { x: anchor.x - 24 - size.width, y: anchor.y - size.height / 2, ...size },
    { x: anchor.x - size.width / 2, y: anchor.y - 24 - size.height, ...size },
    { x: anchor.x - size.width / 2, y: anchor.y + 24, ...size },
  ];
}

export default function PossibleLifeProjection({ work, home, grocery, meaning, livingMeaning, currentJudgment, decisionReadiness, independentKitchen, indoorSoundObservation, meaningfulUnknown, meaningfulUnknownWhy, realityActionLabel, realityActionWhy, realityActionType, publicRentEvidence, publicActionOutcome, feedbackMoveLabel, feedbackMoveWhy, actionExecutionStatus = 'idle', onExecutePublicAction, focused, onToggle, rent, budget, onAskRent, rentSourceAvailable = false, rentLookupStatus = 'idle' }: {
  work: Point & { name: string };
  home: Point & { name: string };
  grocery?: Point & { walkingMinutes: number };
  meaning: string;
  livingMeaning?: string | null;
  currentJudgment?: string | null;
  decisionReadiness?: 'NEED_MORE_REALITY' | 'DECISION_READY' | null;
  independentKitchen?: boolean | null;
  indoorSoundObservation?: string | null;
  meaningfulUnknown?: string | null;
  meaningfulUnknownWhy?: string | null;
  realityActionLabel?: string | null;
  realityActionWhy?: string | null;
  realityActionType?: 'PUBLIC_EVIDENCE' | 'USER_REALITY' | null;
  publicRentEvidence?: {
    source_reference: string; source_title: string; source_provider: string;
    property_text: string; observed_at: string; published_at: string | null;
  } | null;
  publicActionOutcome?: 'NO_EVIDENCE' | null;
  feedbackMoveLabel?: string | null;
  feedbackMoveWhy?: string | null;
  actionExecutionStatus?: 'idle' | 'loading' | 'failed';
  onExecutePublicAction: () => void;
  focused: boolean;
  onToggle: () => void;
  rent: number | null;
  budget: number | null;
  onAskRent: () => void;
  rentSourceAvailable?: boolean;
  rentLookupStatus?: 'idle' | 'loading' | 'failed';
}) {
  const workRef = useRef<HTMLDivElement>(null);
  const homeRef = useRef<HTMLDivElement>(null);
  const timeRef = useRef<HTMLSpanElement>(null);
  const [sizes, setSizes] = useState<Size[] | null>(null);
  useLayoutEffect(() => {
    const elements = [workRef.current, homeRef.current, timeRef.current];
    const measure = () => {
      const next = elements.map(el => ({ width: el?.offsetWidth ?? 0, height: el?.offsetHeight ?? 0 }));
      setSizes(previous => JSON.stringify(previous) === JSON.stringify(next) ? previous : next);
    };
    measure();
    const observer = new ResizeObserver(measure);
    elements.forEach(el => { if (el) observer.observe(el); });
    return () => observer.disconnect();
  }, [work.name, home.name, meaning, focused, rent, budget, independentKitchen, indoorSoundObservation]);

  const midpoint = { x: (work.x + home.x) / 2, y: (work.y + home.y) / 2 };
  const groceryMidpoint = grocery
    ? { x: (home.x + grocery.x) / 2, y: (home.y + grocery.y) / 2 }
    : null;
  const measured = sizes ?? [{ width: 160, height: 44 }, { width: 160, height: 44 }, { width: 110, height: 18 }];
  const timeBox = { x: midpoint.x - measured[2].width / 2, y: midpoint.y - measured[2].height / 2, ...measured[2] };
  const anchors = [work, home].map(p => ({ x: p.x - 14, y: p.y - 14, width: 28, height: 28 }));
  let best: { work: Box; home: Box; collisions: number } | null = null;
  for (const workBox of positions(work, measured[0])) {
    for (const homeBox of positions(home, measured[1])) {
      const collisions = Number(intersects(workBox, homeBox))
        + [workBox, homeBox].reduce((sum, box) => sum
          + Number(intersects(box, timeBox))
          + anchors.filter(anchor => intersects(box, anchor)).length, 0);
      if (!best || collisions < best.collisions) best = { work: workBox, home: homeBox, collisions };
    }
  }
  const workBox = best!.work;
  const homeBox = best!.home;
  const leaderEnd = (anchor: Point, box: Box) => ({
    x: Math.max(box.x, Math.min(anchor.x, box.x + box.width)),
    y: Math.max(box.y, Math.min(anchor.y, box.y + box.height)),
  });

  return (
    <div className="pointer-events-none absolute inset-0" style={{ visibility: sizes ? 'visible' : 'hidden' }}>
      <svg className="absolute inset-0 h-full w-full overflow-visible" aria-hidden="true">
        <line x1={work.x} y1={work.y} x2={home.x} y2={home.y} stroke="currentColor" strokeWidth={focused ? 1.75 : 1} strokeDasharray="4 5" className={focused ? 'text-slate-800/80' : 'text-slate-500/60'} />
        {focused && grocery && <line x1={home.x} y1={home.y} x2={grocery.x} y2={grocery.y} stroke="currentColor" strokeWidth="1" strokeDasharray="2 5" className="text-emerald-800/60" />}
        {[[work, workBox], [home, homeBox]].map(([anchor, box], i) => {
          const end = leaderEnd(anchor, box as Box);
          return <line key={i} x1={anchor.x} y1={anchor.y} x2={end.x} y2={end.y} stroke="currentColor" strokeWidth="0.75" className="text-slate-500/50" />;
        })}
      </svg>
      <span data-world-anchor="work" className={`object-mark absolute -translate-x-1/2 -translate-y-1/2 ${focused ? 'opacity-50' : ''}`} style={{ left: work.x, top: work.y }} aria-hidden="true">●</span>
      <button data-world-anchor="home" type="button" className="object-mark pointer-events-auto absolute -translate-x-1/2 -translate-y-1/2 border-0 bg-transparent p-0" style={{ left: home.x, top: home.y }} aria-label={`${focused ? '退出聚焦' : '聚焦'} ${home.name}锚点`} aria-pressed={focused} onClick={event => { event.stopPropagation(); onToggle(); }}>{focused ? '◉' : '●'}</button>
      {focused && grocery && <span className="object-mark absolute -translate-x-1/2 -translate-y-1/2 text-emerald-800" style={{ left: grocery.x, top: grocery.y }} aria-hidden="true">○</span>}
      <div ref={workRef} data-world-label="work" className={`world-object absolute w-max whitespace-nowrap ${focused ? 'world-object-context' : ''}`} style={{ left: workBox.x, top: workBox.y }} aria-label={`${work.name}，工作`}>
        <span className="object-name">{work.name}</span><span className="object-kicker mt-1">工作</span>
      </div>
      <div ref={homeRef} data-world-label="home" className={`world-object pointer-events-auto absolute w-max whitespace-nowrap ${focused ? 'font-semibold' : ''}`} style={{ left: homeBox.x, top: homeBox.y }}>
        <button type="button" className="world-object border-0 bg-transparent p-0" aria-label={`${focused ? '退出聚焦' : '聚焦'} ${home.name}`} aria-pressed={focused} onClick={event => { event.stopPropagation(); onToggle(); }}>
          <span className="object-name">{home.name}</span><span className="object-kicker mt-1">{focused ? '如果住这里' : '可能住这里'}</span>
        </button>
        {focused && rent === null && rentLookupStatus === 'loading' && <span className="mt-2 text-xs text-slate-600">正在了解实际租金…</span>}
        {focused && rent === null && rentLookupStatus === 'failed' && <span className="mt-2 text-xs text-slate-500">暂未找到可靠的当前租金</span>}
        {focused && rent === null && rentLookupStatus !== 'loading' && <button type="button" className="mt-2 border-0 bg-transparent p-0 text-xs text-slate-600 underline underline-offset-4" onClick={event => { event.stopPropagation(); onAskRent(); }}>实际租金？</button>}
        {rent !== null && <span className="mt-2 text-xs text-slate-800">¥{rent.toLocaleString('en-US')} / 月</span>}
        {rent !== null && rentSourceAvailable && <span className="mt-1 text-xs text-slate-500">来源可查</span>}
        {focused && rent !== null && budget !== null && <>
          <span className="mt-1 text-xs text-slate-500">预算 ¥{budget.toLocaleString('en-US')}</span>
          <span className="mt-1 text-xs text-slate-800">{rentBudgetMeaning(rent, budget)}</span>
        </>}
        {focused && independentKitchen !== null && independentKitchen !== undefined && <span className="mt-2 text-xs text-slate-800">独立厨房 · {independentKitchen ? '有' : '无'}</span>}
        {focused && indoorSoundObservation && <span className="mt-2 max-w-56 whitespace-normal text-left text-xs text-slate-800">室内声音 · {indoorSoundObservation}</span>}
        {focused && livingMeaning && <span className="mt-3 max-w-56 whitespace-normal text-left text-xs leading-relaxed text-slate-600">{livingMeaning}</span>}
        {focused && currentJudgment && <span className="mt-2 max-w-56 whitespace-normal border-l border-slate-400/60 pl-2 text-left text-xs font-medium leading-relaxed text-slate-800">{currentJudgment}</span>}
        {focused && decisionReadiness === 'DECISION_READY' && <span className="mt-2 max-w-56 whitespace-normal text-left text-xs text-slate-600">现在已经可以判断这个选择了</span>}
        {focused && meaningfulUnknown && <span className="mt-3 max-w-56 whitespace-normal text-left text-xs leading-relaxed text-slate-600"><span className="block text-[10px] tracking-[0.08em] text-slate-400">还需要弄清楚</span><span className="mt-1 block">{meaningfulUnknown}</span>{meaningfulUnknownWhy && <span className="mt-1 block text-[11px] text-slate-500">{meaningfulUnknownWhy}</span>}</span>}
        {focused && meaningfulUnknown && realityActionLabel && <span className="mt-3 max-w-56 whitespace-normal text-left text-xs leading-relaxed text-slate-600"><span className="block text-[10px] tracking-[0.08em] text-slate-400">下一步</span>{realityActionType === 'PUBLIC_EVIDENCE' && !publicRentEvidence ? <button type="button" disabled={actionExecutionStatus === 'loading'} className="mt-1 block border-0 bg-transparent p-0 text-left underline underline-offset-4 disabled:no-underline" onClick={event => { event.stopPropagation(); onExecutePublicAction(); }}>{realityActionLabel}</button> : <span className="mt-1 block">{realityActionLabel}</span>}{realityActionWhy && <span className="mt-1 block text-[11px] text-slate-500">{realityActionWhy}</span>}{actionExecutionStatus === 'loading' && <span className="mt-1 block text-[11px]">正在获取公开证据…</span>}{actionExecutionStatus === 'failed' && <span className="mt-1 block text-[11px]">暂未获得可追溯证据</span>}</span>}
        {focused && publicActionOutcome === 'NO_EVIDENCE' && <span className="mt-2 max-w-56 whitespace-normal text-left text-[11px] leading-relaxed text-slate-500"><span className="block">暂未获得可追溯证据</span>{feedbackMoveLabel && <span className="mt-2 block"><span className="block text-[10px] tracking-[0.08em] text-slate-400">接下来</span><span className="mt-1 block text-slate-700">{feedbackMoveLabel}</span>{feedbackMoveWhy && <span className="mt-1 block">{feedbackMoveWhy}</span>}</span>}</span>}
        {focused && publicRentEvidence && realityActionType === 'PUBLIC_EVIDENCE' && <span className="mt-2 max-w-56 whitespace-normal text-left text-[11px] leading-relaxed text-slate-600"><span className="block text-slate-500">公开证据 · 尚未确认为租金现实</span><a className="pointer-events-auto mt-1 block break-all underline underline-offset-2" href={publicRentEvidence.source_reference} target="_blank" rel="noopener noreferrer" onClick={event => event.stopPropagation()}>{publicRentEvidence.source_title}</a><span className="mt-1 block">{publicRentEvidence.property_text.slice(0, 240)}</span><span className="mt-1 block text-slate-400">获取于 {publicRentEvidence.observed_at}</span></span>}
      </div>
      <span ref={timeRef} data-world-label="time" className={`absolute w-max whitespace-nowrap text-xs text-slate-700 ${focused ? 'font-semibold' : 'opacity-70'}`} style={{ left: timeBox.x, top: timeBox.y }} aria-label={`${home.name}到${work.name}：${meaning}`}>{meaning}</span>
      {focused && grocery && groceryMidpoint && <span className="absolute w-max -translate-x-1/2 -translate-y-1/2 whitespace-nowrap text-center text-xs text-emerald-900" style={{ left: groceryMidpoint.x, top: groceryMidpoint.y }} aria-label={`日常采购，步行 ${grocery.walkingMinutes} 分钟`}><span className="block font-medium">日常采购</span><span className="mt-1 block opacity-75">步行 {grocery.walkingMinutes}min</span></span>}
    </div>
  );
}
