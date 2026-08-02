import { apiFetch, apiRequest } from './api';
import type { ChatRequest, ChatResponse } from '@/types/chat';

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

    const response = await apiRequest('/chat/stream', {
        method: 'POST',
        cache: 'no-store',
        headers: {
            Accept: 'text/event-stream',
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
    let eventBuffer = '';

    const processEvents = (value: string) => {
        eventBuffer += value.replaceAll('\r\n', '\n');
        const events = eventBuffer.split('\n\n');
        eventBuffer = events.pop() ?? '';

        for (const event of events) {
            const data = event
                .split('\n')
                .find((line) => line.startsWith('data: '));

            if (!data) {
                continue;
            }

            const chunk: unknown = JSON.parse(data.slice(6));
            if (typeof chunk !== 'string') {
                throw new Error('Streaming API returned an invalid event.');
            }
            onChunk(chunk);
        }
    };

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
                processEvents(chunk);
            }
        }

        const remaining = decoder.decode();
        if (remaining) {
            processEvents(remaining);
        }
        if (eventBuffer.trim()) {
            processEvents('\n\n');
        }
    } finally {
        reader.releaseLock();
    }
}
