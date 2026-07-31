'use client';

import { motion } from 'framer-motion';

export type AICoreState =
  | 'idle'
  | 'listening'
  | 'thinking'
  | 'understanding'
  | 'decision'
  | 'completed'
  | 'error';

export type AICoreSize = 'hero' | 'runtime';

interface AICoreProps {
  state?: AICoreState;
  size?: AICoreSize;
}

const STATE_STYLES: Record<
  AICoreState,
  {
    glow: string;
    core: string;
    duration: number;
    glowScale: number;
    glowOpacity: number;
    orbitDuration: number;
  }
> = {
  idle: {
    glow: 'bg-blue-400/20',
    core: 'from-[#d9efff] via-[#79b8ef] to-[#245eaa]',
    duration: 3.4,
    glowScale: 1.04,
    glowOpacity: 0.64,
    orbitDuration: 22,
  },
  listening: {
    glow: 'bg-blue-400/25',
    core: 'from-[#d5efff] via-[#64acee] to-[#205ba7]',
    duration: 2.8,
    glowScale: 1.07,
    glowOpacity: 0.76,
    orbitDuration: 18,
  },
  thinking: {
    glow: 'bg-violet-400/28',
    core: 'from-[#e1dcff] via-[#8a75e8] to-[#4838a4]',
    duration: 2,
    glowScale: 1.1,
    glowOpacity: 0.86,
    orbitDuration: 12,
  },
  understanding: {
    glow: 'bg-blue-400/25',
    core: 'from-[#d8f1ff] via-[#6daee8] to-[#4a58bd]',
    duration: 2.5,
    glowScale: 1.08,
    glowOpacity: 0.8,
    orbitDuration: 15,
  },
  decision: {
    glow: 'bg-violet-400/30',
    core: 'from-[#e4e3ff] via-[#867de8] to-[#3f439e]',
    duration: 2.6,
    glowScale: 1.06,
    glowOpacity: 0.9,
    orbitDuration: 16,
  },
  completed: {
    glow: 'bg-blue-400/20',
    core: 'from-[#d8efff] via-[#72afe1] to-[#2f6ba6]',
    duration: 3.2,
    glowScale: 1.04,
    glowOpacity: 0.68,
    orbitDuration: 22,
  },
  error: {
    glow: 'bg-rose-400/22',
    core: 'from-[#ffe1e7] via-[#cd7086] to-[#7f334e]',
    duration: 2.2,
    glowScale: 1.06,
    glowOpacity: 0.76,
    orbitDuration: 24,
  },
};

export default function AICore({
  state = 'idle',
  size = 'hero',
}: AICoreProps) {
  const style = STATE_STYLES[state];
  const isRuntimeSize = size === 'runtime';

  return (
    <motion.div
      aria-label={`AI Core: ${state}`}
      data-core-state={state}
      className={[
        'relative flex shrink-0 items-center justify-center',
        isRuntimeSize ? 'h-9 w-9' : 'h-40 w-40',
      ].join(' ')}
      animate={{ opacity: 1 }}
      initial={false}
      transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
    >
      <motion.div
        className={[
          'absolute rounded-full blur-3xl transition-colors duration-500',
          style.glow,
          isRuntimeSize ? 'h-9 w-9 blur-md' : 'h-32 w-32',
        ].join(' ')}
        animate={{
          scale: [1, style.glowScale, 1],
          opacity: [0.42, style.glowOpacity, 0.42],
        }}
        transition={{
          duration: style.duration,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
      />

      <motion.div
        className={[
          'absolute rounded-full border border-blue-100/20',
          isRuntimeSize ? 'h-7 w-7' : 'h-24 w-24',
        ].join(' ')}
        animate={{ rotate: 360 }}
        transition={{
          duration: style.orbitDuration,
          repeat: Infinity,
          ease: 'linear',
        }}
      >
        <span className="absolute left-1/2 top-[-1px] h-1 w-1 -translate-x-1/2 rounded-full bg-blue-100/60" />
      </motion.div>

      <motion.div
        className={[
          'relative overflow-hidden rounded-full bg-gradient-to-br transition-colors duration-500',
          style.core,
          isRuntimeSize
            ? 'h-4 w-4 shadow-[inset_-3px_-4px_7px_rgba(5,15,45,0.55),inset_2px_2px_4px_rgba(220,242,255,0.45),0_0_14px_rgba(91,166,230,0.5)]'
            : 'h-14 w-14 shadow-[inset_-10px_-12px_22px_rgba(5,15,45,0.58),inset_7px_7px_13px_rgba(220,242,255,0.42),0_0_34px_rgba(91,166,230,0.52)]',
        ].join(' ')}
        animate={{ scale: [0.98, 1.035, 0.98] }}
        transition={{
          duration: style.duration,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
      >
        <span className="absolute inset-[18%] rounded-full bg-blue-50/20 blur-[2px]" />
      </motion.div>
    </motion.div>
  );
}
