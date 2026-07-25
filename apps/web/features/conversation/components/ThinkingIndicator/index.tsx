'use client';

import { motion } from 'framer-motion';

const dots = [0, 1, 2];

export default function ThinkingIndicator() {
    return (
        <div
            role="status"
            aria-live="polite"
            aria-label="LiveOS is thinking"
            className="mb-6 flex justify-start"
        >
            <div className="flex items-center gap-3 rounded-3xl bg-neutral-900 px-5 py-4 text-neutral-300">
                <div className="flex items-center gap-1">
                    {dots.map((dot) => (
                        <motion.span
                            key={dot}
                            className="h-1.5 w-1.5 rounded-full bg-neutral-400"
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

                <span className="text-sm">LiveOS is thinking...</span>
            </div>
        </div>
    );
}