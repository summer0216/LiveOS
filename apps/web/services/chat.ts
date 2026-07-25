import { apiFetch } from './api';
import type { ChatRequest, ChatResponse } from '@/types/chat';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://127.0.0.1:8000/api';

export async function sendMessage(
    conversationId: string,
    message: string,
): Promise<ChatResponse> {
    const request: ChatRequest = {
        conversation_id: conversationId,
        message,
    };

    return apiFetch<ChatResponse>('/chat', {
        method: 'POST',
        body: JSON.stringify(request),
    });
}

interface StreamMessageOptions {
    conversationId: string;
    message: string;
    onChunk: (chunk: string) => void;

}

export async function streamMessage({
    conversationId,
    message,
    onChunk,
}: StreamMessageOptions): Promise<void> {
    const request: ChatRequest = {
        conversation_id: conversationId,
        message,
    };

    const response = await fetch(`${API_BASE_URL}/chat/stream`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
    });

    if (!response.ok) {
        throw new Error(`Streaming API error: ${response.status}`);
    }

    if (!response.body) {
        throw new Error('Streaming response body is unavailable.');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    try {
        while (true) {
            const { value, done } = await reader.read();
            if (done) {
                break;
            }

            const chunk = decoder.decode(value, {
                stream: true,
            });
            if (chunk) {
                onChunk(chunk);
            }

        }

        const remaining = decoder.decode();
        if (remaining) {
            onChunk(remaining);
        }

    } finally {
        reader.releaseLock();
    }

}