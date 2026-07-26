'use client';

import type { KeyboardEvent } from 'react';
import { useState } from 'react';

interface ConversationComposerProps {
    disabled?: boolean;
    onSubmit: (message: string) => void;
}

export default function ConversationComposer({
    disabled = false,
    onSubmit,
}: ConversationComposerProps) {
    const [message, setMessage] = useState('');

    const submit = () => {
        const value = message.trim();

        if (!value || disabled) {
            return;
        }

        onSubmit(value);
        setMessage('');
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
        <div className="sticky bottom-0 mt-8 border-t border-white/10 bg-black/90 px-1 py-5 backdrop-blur-xl">
            <div className="flex items-end gap-3 rounded-3xl border border-white/10 bg-white/5 p-3">
                <textarea
                    rows={1}
                    value={message}
                    disabled={disabled}
                    onChange={(event) => setMessage(event.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Continue the conversation..."
                    className="max-h-36 min-h-12 flex-1 resize-none bg-transparent px-3 py-3 text-white outline-none placeholder:text-neutral-500 disabled:cursor-not-allowed disabled:opacity-50"
                />

                <button
                    type="button"
                    disabled={disabled || !message.trim()}
                    onClick={submit}
                    className="rounded-full bg-white px-5 py-3 text-sm font-medium text-black transition hover:bg-neutral-200 disabled:cursor-not-allowed disabled:opacity-40"
                >
                    Send
                </button>
            </div>

            <p className="mt-2 text-center text-xs text-neutral-600">
                Enter to send · Shift + Enter for a new line
            </p>
        </div>
    );
}