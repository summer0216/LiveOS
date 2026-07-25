import { apiFetch } from './api';
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