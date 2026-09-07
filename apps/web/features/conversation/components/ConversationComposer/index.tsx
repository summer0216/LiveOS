'use client';

import type { KeyboardEvent } from 'react';
import { useState } from 'react';
import { Send } from 'lucide-react';

interface ConversationComposerProps {
    disabled?: boolean;
    variant?: 'default' | 'ambient';
    onSubmit: (message: string) => void;
    onListeningChange: (isListening: boolean) => void;
}

export default function ConversationComposer({
    disabled = false,
    variant = 'default',
    onSubmit,
    onListeningChange,
}: ConversationComposerProps) {
    const [message, setMessage] = useState('');
    const isAmbient = variant === 'ambient';

    const submit = () => {
        const value = message.trim();

        if (!value || disabled) {
            return;
        }

        onSubmit(value);
        setMessage('');
        onListeningChange(false);
    };

    const handleKeyDown = (
        event: KeyboardEvent<HTMLTextAreaElement>,
    ) => {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            submit();
        }
    };

    return (
        <div
            className={
                isAmbient
                    ? 'shrink-0'
                    : 'shrink-0 border-t border-white/[0.06] bg-[#050812]/95 px-5 py-5 backdrop-blur-xl sm:px-8'
            }
        >
            <div
                className={
                    isAmbient
                        ? 'flex items-end gap-3 rounded-2xl border border-slate-700/10 bg-white/55 p-2.5 backdrop-blur-md transition-[background-color,border-color] duration-200 hover:border-slate-700/20 hover:bg-white/70 focus-within:border-slate-700/30 focus-within:bg-white/90'
                        : 'flex items-end gap-3 rounded-xl border border-white/10 bg-[#10182b] p-2.5 transition-[background-color,border-color,box-shadow] duration-200 hover:border-blue-400/50 hover:bg-[#121c31] focus-within:border-blue-500 focus-within:bg-[#10182b] focus-within:shadow-[0_0_0_4px_rgba(59,105,255,0.12)]'
                }
            >
                <textarea
                    rows={1}
                    value={message}
                    disabled={disabled}
                    onChange={(event) => {
                        const nextMessage = event.target.value;
                        setMessage(nextMessage);
                        onListeningChange(Boolean(nextMessage.trim()));
                    }}
                    onKeyDown={handleKeyDown}
                    placeholder="告诉 LiveOS 新情况……"
                    className={
                        isAmbient
                            ? 'max-h-32 min-h-11 flex-1 resize-none bg-transparent px-3 py-3 text-sm text-slate-700 outline-none placeholder:text-slate-500 disabled:cursor-not-allowed disabled:opacity-50'
                            : 'max-h-32 min-h-11 flex-1 resize-none bg-transparent px-3 py-3 text-sm text-slate-200 outline-none placeholder:text-slate-600 disabled:cursor-not-allowed disabled:opacity-50'
                    }
                />

                <button
                    type="button"
                    aria-label="发送消息"
                    disabled={disabled || !message.trim()}
                    onClick={submit}
                    className={
                        isAmbient
                            ? 'flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-800/75 text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-transparent disabled:text-slate-400'
                            : 'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-blue-500 text-white transition hover:bg-blue-400 disabled:cursor-not-allowed disabled:bg-slate-800 disabled:text-slate-600'
                    }
                >
                    <Send size={16} />
                </button>
            </div>

            <p
                className={
                    isAmbient
                        ? 'mt-2 text-center font-mono text-[10px] text-slate-500'
                        : 'mt-2 text-center font-mono text-[10px] text-slate-700'
                }
            >
                Enter 发送 · Shift + Enter 换行
            </p>
        </div>
    );
}
