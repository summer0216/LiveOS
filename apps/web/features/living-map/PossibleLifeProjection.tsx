'use client';

import { useLayoutEffect, useRef, useState } from 'react';

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

export default function PossibleLifeProjection({ work, home, meaning, focused, onToggle }: {
  work: Point & { name: string };
  home: Point & { name: string };
  meaning: string;
  focused: boolean;
  onToggle: () => void;
}) {
  const workRef = useRef<HTMLDivElement>(null);
  const homeRef = useRef<HTMLButtonElement>(null);
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
  }, [work.name, home.name, meaning, focused]);

  const midpoint = { x: (work.x + home.x) / 2, y: (work.y + home.y) / 2 };
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
        {[[work, workBox], [home, homeBox]].map(([anchor, box], i) => {
          const end = leaderEnd(anchor, box as Box);
          return <line key={i} x1={anchor.x} y1={anchor.y} x2={end.x} y2={end.y} stroke="currentColor" strokeWidth="0.75" className="text-slate-500/50" />;
        })}
      </svg>
      <span data-world-anchor="work" className={`object-mark absolute -translate-x-1/2 -translate-y-1/2 ${focused ? 'opacity-50' : ''}`} style={{ left: work.x, top: work.y }} aria-hidden="true">●</span>
      <button data-world-anchor="home" type="button" className="object-mark pointer-events-auto absolute -translate-x-1/2 -translate-y-1/2 border-0 bg-transparent p-0" style={{ left: home.x, top: home.y }} aria-label={`${focused ? '退出聚焦' : '聚焦'} ${home.name}锚点`} aria-pressed={focused} onClick={event => { event.stopPropagation(); onToggle(); }}>{focused ? '◉' : '●'}</button>
      <div ref={workRef} data-world-label="work" className={`world-object absolute w-max whitespace-nowrap ${focused ? 'world-object-context' : ''}`} style={{ left: workBox.x, top: workBox.y }} aria-label={`${work.name}，工作`}>
        <span className="object-name">{work.name}</span><span className="object-kicker mt-1">工作</span>
      </div>
      <button ref={homeRef} data-world-label="home" type="button" className={`world-object pointer-events-auto absolute w-max whitespace-nowrap border-0 bg-transparent p-0 ${focused ? 'font-semibold' : ''}`} style={{ left: homeBox.x, top: homeBox.y }} aria-label={`${focused ? '退出聚焦' : '聚焦'} ${home.name}`} aria-pressed={focused} onClick={event => { event.stopPropagation(); onToggle(); }}>
        <span className="object-name">{home.name}</span><span className="object-kicker mt-1">{focused ? '如果住这里' : '可能住这里'}</span>
      </button>
      <span ref={timeRef} data-world-label="time" className={`absolute w-max whitespace-nowrap text-xs text-slate-700 ${focused ? 'font-semibold' : 'opacity-70'}`} style={{ left: timeBox.x, top: timeBox.y }} aria-label={`${home.name}到${work.name}：${meaning}`}>{meaning}</span>
    </div>
  );
}
