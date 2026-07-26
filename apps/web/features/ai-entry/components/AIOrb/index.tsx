'use client';

import { motion } from 'framer-motion';

export type AIOrbState =
  | 'idle'
  | 'thinking'
  | 'streaming';

interface AIOrbProps {
  state?: AIOrbState;
}

export default function AIOrb({
  state = 'idle',
}: AIOrbProps) {
  const animation =
    state === 'thinking'
      ? {
        scale: [1, 1.12, 1],
        opacity: [0.4, 0.9, 0.4],
      }
      : state === 'streaming'
        ? {
          scale: [1, 1.18, 1],
          opacity: [0.5, 1, 0.5],
        }
        : {
          scale: [1, 1.06, 1],
          opacity: [0.5, 0.8, 0.5],
        };

  return (
    <div className="relative flex h-40 w-40 items-center justify-center">
      {/* Glow */}
      <motion.div
        className="absolute h-32 w-32 rounded-full bg-cyan-400/20 blur-3xl"
        animate={animation}
        transition={{
          duration: 3,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
      />

      {/* Ring */}
      <motion.div
        className="absolute h-24 w-24 rounded-full border border-white/20"
        animate={{
          rotate: 360,
        }}
        transition={{
          duration: 18,
          repeat: Infinity,
          ease: 'linear',
        }}
      />

      {/* Core */}
      <motion.div
        className="relative h-14 w-14 rounded-full bg-white shadow-[0_0_40px_rgba(255,255,255,.8)]"
        animate={{
          scale: [0.95, 1.05, 0.95],
        }}
        transition={{
          duration: 2.5,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
      />
    </div>
  );
}