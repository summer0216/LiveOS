import { apiFetch } from "./api";

export interface ChatRequest {
    message: string;
}

export interface ChatResponse {
    reply: string;
}

export async function sendMessage(
    message: string
): Promise<ChatResponse> {
    return apiFetch<ChatResponse>(
        "/chat",
        {
            method: "POST",
            body: JSON.stringify({
                message,
            }),
        }
    );
}