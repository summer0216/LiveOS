'use client';

import { motion, useReducedMotion } from 'framer-motion';

export type AICoreState =
  | 'idle'
  | 'listening'
  | 'thinking'
  | 'understanding'
  | 'decision'
  | 'completed'
  | 'error';

export type AICoreSize = 'hero' | 'sm';

interface AICoreProps {
  state?: AICoreState;
  size?: AICoreSize;
}

interface HeroPalette {
  blue: string;
  purple: string;
  sphereLight: string;
  sphereMid: string;
  sphereEdge: string;
}

// Idle is the exact source palette from AI_Core.md. The remaining entries
// preserve the same material relationship for the existing runtime states.
const HERO_PALETTES: Record<AICoreState, HeroPalette> = {
  idle: { blue: '#4F7FFF', purple: '#7C5FFF', sphereLight: '#7C5FFF', sphereMid: '#5A72FF', sphereEdge: '#1A1060' },
  listening: { blue: '#3ECFFF', purple: '#4F7FFF', sphereLight: '#4F7FFF', sphereMid: '#3ECFFF', sphereEdge: '#17235F' },
  thinking: { blue: '#8B5CF6', purple: '#C084FC', sphereLight: '#C084FC', sphereMid: '#8B5CF6', sphereEdge: '#25155F' },
  understanding: { blue: '#5C83FF', purple: '#806FFF', sphereLight: '#806FFF', sphereMid: '#5C83FF', sphereEdge: '#1C2168' },
  decision: { blue: '#756CFF', purple: '#A084FF', sphereLight: '#A084FF', sphereMid: '#756CFF', sphereEdge: '#241760' },
  completed: { blue: '#4F8CDB', purple: '#6F9BE9', sphereLight: '#719EEA', sphereMid: '#4F8CDB', sphereEdge: '#193A6B' },
  error: { blue: '#C56782', purple: '#A64D68', sphereLight: '#CE708B', sphereMid: '#A64D68', sphereEdge: '#542235' },
};

const COLOR_TRANSITION = { duration: 0.8, ease: [0.22, 1, 0.36, 1] as const };
const SMALL_DIAMETER = 36;
const SMALL_HALO_INSET = SMALL_DIAMETER * 0.35;
const SMALL_GLOW_RADIUS = SMALL_DIAMETER * 0.5;
const SMALL_HIGHLIGHT_BLUR = SMALL_DIAMETER * 0.06;

export default function AICore({
  state = 'idle',
  size = 'hero',
}: AICoreProps) {
  const hero = HERO_PALETTES[state];
  const isSmallSize = size === 'sm';
  const reduceMotion = useReducedMotion();
  const motionPaused = Boolean(reduceMotion) || state === 'error';
  const heroMotion = !isSmallSize && !motionPaused;

  const heroSphereBackground = [
    `radial-gradient(ellipse 80% 80% at 78% 82%, ${hero.blue}4F 0%, transparent 55%)`,
    `radial-gradient(ellipse 120% 120% at 36% 32%, ${hero.sphereLight} 0%, ${hero.sphereMid} 28%, ${hero.blue}88 50%, ${hero.sphereEdge} 72%, #06040f 100%)`,
  ].join(', ');

  if (isSmallSize) {
    return (
      <motion.div
        aria-label={`AI Core: ${state}`}
        data-core-size={size}
        data-core-state={state}
        className="relative flex shrink-0 items-center justify-center"
        style={{ height: SMALL_DIAMETER, width: SMALL_DIAMETER }}
        initial={{ opacity: 1 }}
        animate={{ opacity: 1 }}
        transition={COLOR_TRANSITION}
      >
        <motion.div
          aria-hidden="true"
          className="absolute rounded-full"
          style={{
            inset: -SMALL_HALO_INSET,
            background: `radial-gradient(circle, ${hero.blue}0E 0%, transparent 65%)`,
          }}
          initial={{ scale: 1, opacity: 0.3 }}
          animate={motionPaused
            ? { scale: 1, opacity: 0.3 }
            : { scale: [1, 1.08, 1], opacity: [0.3, 0.6, 0.3] }}
          transition={{ duration: 3, repeat: motionPaused ? 0 : Infinity, ease: 'easeInOut' }}
        />
        <motion.div
          aria-hidden="true"
          className="relative h-full w-full overflow-hidden rounded-full"
          style={{
            background: heroSphereBackground,
            boxShadow: `0 0 ${SMALL_GLOW_RADIUS}px ${hero.blue}54, inset ${SMALL_DIAMETER * 0.1375}px ${SMALL_DIAMETER * 0.18125}px ${SMALL_DIAMETER * 0.38125}px rgba(0, 0, 0, 0.72), inset -${SMALL_DIAMETER * 0.0625}px -${SMALL_DIAMETER * 0.08125}px ${SMALL_DIAMETER * 0.21875}px ${hero.purple}29`,
          }}
          initial={{ scale: 1 }}
          animate={{ scale: motionPaused ? 1 : [1, 1.025, 1] }}
          transition={{ duration: 3, repeat: motionPaused ? 0 : Infinity, ease: 'easeInOut' }}
        >
          <span
            className="absolute inset-0 rounded-full"
            style={{ background: `radial-gradient(ellipse 55% 40% at 82% 78%, ${hero.blue}61 0%, transparent 60%)` }}
          />
          <span
            className="absolute left-[20%] top-[15%] h-[14%] w-[20%] rounded-full bg-white/[0.92]"
            style={{ filter: `blur(${SMALL_HIGHLIGHT_BLUR}px)` }}
          />
        </motion.div>
      </motion.div>
    );
  }

  return (
    <div
      aria-label={`AI Core: ${state}`}
      data-core-size={size}
      data-core-state={state}
      className="relative flex h-40 w-40 shrink-0 items-center justify-center"
    >
      {/* halo-outer: inset -80px, 3s */}
      <motion.span
        initial={{ opacity: 0.3, scale: 1 }}
        aria-hidden="true"
        className="absolute h-80 w-80 rounded-full"
        style={{ background: `radial-gradient(circle, ${hero.blue}0E 0%, transparent 65%)` }}
        animate={heroMotion ? { opacity: [0.3, 0.6, 0.3], scale: [1, 1.08, 1] } : { opacity: 0.3, scale: 1 }}
        transition={{ duration: 3, repeat: heroMotion ? Infinity : 0, ease: 'easeInOut' }}
      />

      {/* halo-mid: inset -29px, 3s, delayed 0.6s */}
      <motion.span
        initial={{ opacity: 0.2, scale: 1 }}
        aria-hidden="true"
        className="absolute h-[218px] w-[218px] rounded-full"
        style={{ background: `radial-gradient(circle, ${hero.blue}1A 0%, transparent 70%)` }}
        animate={heroMotion ? { opacity: [0.2, 0.5, 0.2], scale: [1, 1.05, 1] } : { opacity: 0.2, scale: 1 }}
        transition={{ duration: 3, delay: heroMotion ? 0.6 : 0, repeat: heroMotion ? Infinity : 0, ease: 'easeInOut' }}
      />

      {/* contact-shadow: synchronized with the sphere float */}
      <motion.span
        initial={{ opacity: 0.5, scaleX: 1 }}
        aria-hidden="true"
        className="absolute -bottom-[35px] left-[15%] h-[19px] w-[70%] rounded-full blur-[13px]"
        style={{ background: 'radial-gradient(ellipse, rgba(0, 0, 0, 0.55) 0%, transparent 70%)' }}
        animate={heroMotion ? { opacity: [0.5, 0.2, 0.5], scaleX: [1, 0.65, 1] } : { opacity: 0.5, scaleX: 1 }}
        transition={{ duration: 4, repeat: heroMotion ? Infinity : 0, ease: 'easeInOut' }}
      />

      {/* sphere-group: only the sphere moves; rings remain fixed on root */}
      <motion.span
        initial={{ y: 0 }}
        aria-hidden="true"
        className="absolute inset-0 z-10"
        animate={{ y: heroMotion ? [0, -12, 0] : 0 }}
        transition={{ duration: 4, repeat: heroMotion ? Infinity : 0, ease: 'easeInOut' }}
      >
        <span
          className="absolute inset-0 overflow-hidden rounded-full"
          style={{
            background: heroSphereBackground,
            boxShadow: `0 0 80px ${hero.blue}54, 0 0 176px ${hero.blue}1A, inset 22px 29px 61px rgba(0, 0, 0, 0.72), inset -10px -13px 35px ${hero.purple}29`,
          }}
        >
          <span
            className="absolute inset-0 rounded-full"
            style={{ background: `radial-gradient(ellipse 55% 40% at 82% 78%, ${hero.blue}61 0%, transparent 60%)` }}
          />
          <span className="absolute left-[14%] top-[11%] h-[30%] w-[42%] rotate-[-18deg] rounded-full bg-white/55 blur-[12px]" />
          <span className="absolute left-[20%] top-[15%] h-[14%] w-[20%] rounded-full bg-white/[0.92] blur-[4px]" />
        </span>
      </motion.span>

      {/* ring-1: clockwise 10s */}
      <motion.span
        initial={{ rotate: 0 }}
        aria-hidden="true"
        className="absolute -inset-[14px] rounded-full border"
        style={{ borderColor: `${hero.blue}29` }}
        animate={{ rotate: heroMotion ? 360 : 0 }}
        transition={{ duration: 10, repeat: heroMotion ? Infinity : 0, ease: 'linear' }}
      >
        <span
          className="absolute -top-[5px] left-[48%] h-[10px] w-[10px] rounded-full"
          style={{ background: hero.blue, boxShadow: `0 0 10px ${hero.blue}, 0 0 20px ${hero.blue}80` }}
        />
      </motion.span>

      {/* ring-2: counter-clockwise 16s */}
      <motion.span
        initial={{ rotate: 0 }}
        aria-hidden="true"
        className="absolute -inset-[28px] rounded-full border"
        style={{ borderColor: `${hero.purple}14` }}
        animate={{ rotate: heroMotion ? -360 : 0 }}
        transition={{ duration: 16, repeat: heroMotion ? Infinity : 0, ease: 'linear' }}
      >
        <span className="absolute -bottom-[4px] right-[30%] h-[6px] w-[6px] rounded-full opacity-70" style={{ background: hero.purple }} />
      </motion.span>

      {/* three source ping rings: 3s, 0 / 1.2 / 2.4s */}
      {[0, 1, 2].map((wave) => (
        <motion.span
          initial={{ opacity: 0.45, scale: 1 }}
          key={wave}
          aria-hidden="true"
          className="absolute -inset-[16px] rounded-full border"
          style={{ borderColor: `${hero.blue}2B` }}
          animate={heroMotion ? { opacity: [0.45, 0], scale: [1, 2.4] } : { opacity: 0.45, scale: 1 }}
          transition={{ duration: 3, delay: heroMotion ? wave * 1.2 : 0, repeat: heroMotion ? Infinity : 0, ease: 'easeOut' }}
        />
      ))}
    </div>
  );
}
