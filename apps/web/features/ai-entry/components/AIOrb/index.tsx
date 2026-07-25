'use client';

import { motion } from 'framer-motion';

export default function AIOrb() {
  return (
    <div
      className="relative flex h-40 w-40 items-center justify-center"
      aria-label="LiveOS AI Core"
    >
      <motion.div
        className="absolute h-32 w-32 rounded-full bg-white/10 blur-3xl"
        animate={{
          scale: [0.9, 1.15, 0.9],
          opacity: [0.25, 0.55, 0.25],
        }}
        transition={{
          duration: 4,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
      />

      <motion.div
        className="absolute h-24 w-24 rounded-full border border-white/20 bg-white/5 shadow-[0_0_80px_rgba(255,255,255,0.18)] backdrop-blur-xl"
        animate={{
          scale: [1, 1.06, 1],
          y: [0, -4, 0],
          opacity: [0.85, 1, 0.85],
        }}
        transition={{
          duration: 4,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
      />

      <motion.div
        className="relative h-12 w-12 rounded-full bg-white shadow-[0_0_36px_rgba(255,255,255,0.75)]"
        animate={{
          scale: [0.96, 1.05, 0.96],
          opacity: [0.9, 1, 0.9],
        }}
        transition={{
          duration: 3.2,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
      />
    </div>
  );
}