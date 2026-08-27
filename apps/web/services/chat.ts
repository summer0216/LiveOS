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
  onDecisionRelevantFeedback?: () => void;
  onDecisionChange?: (change: DecisionChange) => void;
}

export interface DecisionChangeCause {
  source:
    | 'PROFILE_MUTATION'
    | 'DECISION_RELEVANT_FEEDBACK'
    | 'DECISION_CHALLENGE'
    | 'VERIFICATION_OUTCOME';
  field?: string;
  operation?: 'SET' | 'CLEAR';
  before?: string | number | boolean | null;
  after?: string | number | boolean | null;
  observation?: string;
  judgment?: 'acceptable' | 'unacceptable' | null;
  observed_commute_minutes?: number | null;
  kind?: 'DIRECT' | 'TRADE_OFF' | 'PRIORITY' | 'ALTERNATIVE';
  subject?: string | null;
  statement?: string;
  target_property_id?: string | null;
  status?: 'CONFIRMED' | 'DISCONFIRMED' | 'INCONCLUSIVE';
  evidence?: Array<Record<string, string | number>>;
}

export interface DecisionChange {
  causes: DecisionChangeCause[];
  explanation: string;
}

function isDecisionChange(value: unknown): value is DecisionChange {
  if (typeof value !== 'object' || value === null) return false;
  const candidate = value as Partial<DecisionChange>;
  return (
    Array.isArray(candidate.causes) &&
    candidate.causes.length > 0 &&
    typeof candidate.explanation === 'string' &&
    candidate.explanation.trim().length > 0
  );
}

const STREAM_READ_TIMEOUT_MS = 90_000;

export async function streamMessage({
  conversationId,
  message,
  onChunk,
  onDecisionRelevantFeedback,
  onDecisionChange,
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
      const eventType = event
        .split('\n')
        .find((line) => line.startsWith('event: '));
      const data = event.split('\n').find((line) => line.startsWith('data: '));

      if (!data) {
        continue;
      }

      const chunk: unknown = JSON.parse(data.slice(6));
      if (eventType === 'event: decision-change') {
        if (isDecisionChange(chunk)) {
          onDecisionChange?.(chunk);
          continue;
        }
        throw new Error('Streaming API returned an invalid decision change.');
      }
      if (eventType === 'event: decision-feedback') {
        if (chunk === true) {
          onDecisionRelevantFeedback?.();
          continue;
        }
        throw new Error('Streaming API returned an invalid feedback event.');
      }
      if (typeof chunk !== 'string') {
        throw new Error('Streaming API returned an invalid event.');
      }
      if (eventType === 'event: error') {
        throw new Error(chunk);
      }
      onChunk(chunk);
    }
  };

  try {
    while (true) {
      let readTimeout: ReturnType<typeof setTimeout> | undefined;
      const { value, done } = await Promise.race([
        reader.read().finally(() => {
          if (readTimeout !== undefined) {
            clearTimeout(readTimeout);
          }
        }),
        new Promise<never>((_, reject) => {
          readTimeout = setTimeout(() => {
            void reader.cancel();
            reject(
              new Error('Streaming response timed out while waiting for data.'),
            );
          }, STREAM_READ_TIMEOUT_MS);
        }),
      ]);
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
