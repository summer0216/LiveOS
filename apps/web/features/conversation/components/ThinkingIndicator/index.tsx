'use client';

import { motion } from 'framer-motion';

import { AIAvatar } from '../MessageBubble';

const dots = [0, 1, 2];

export default function ThinkingIndicator() {
    return (
        <motion.div
            role="status"
            aria-live="polite"
            aria-label="LiveOS 正在思考"
            className="mb-8 flex items-start gap-3 sm:gap-4"
            initial={{ opacity: 0, y: 2 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.18, ease: 'easeOut' }}
        >
            <AIAvatar />
            <div className="flex min-h-[60px] items-center gap-3 rounded-2xl border border-white/[0.08] bg-[#0b1020] px-6 py-4 text-slate-400">
                <div className="flex items-center gap-1">
                    {dots.map((dot) => (
                        <motion.span
                            key={dot}
                            className="h-1.5 w-1.5 rounded-full bg-blue-400"
                            animate={{
                                opacity: [0.35, 1, 0.35],
                                y: [0, -3, 0],
                            }}
                            transition={{
                                duration: 1.2,
                                repeat: Infinity,
                                delay: dot * 0.18,
                                ease: 'easeInOut',
                            }}
                        />
                    ))}
                </div>

                <span className="text-sm">LiveOS 正在思考…</span>
            </div>
        </motion.div>
    );
}
