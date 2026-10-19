'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { createClientId } from '@/lib/createClientId';
import { getConversationHistory, streamMessage } from '../infrastructure/conversationApi';
import { appendAssistantChunk, restoreConversationMessages } from './conversationMessages';

export function useConversationSession(initialConversationId: string) {
  const [conversationId, setConversationId] = useState(initialConversationId);
  const [messages, setMessages] = useState(() => [] as ReturnType<typeof restoreConversationMessages>);
  const [isRestoring, setIsRestoring] = useState(Boolean(initialConversationId));
  const [isResponding, setIsResponding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const activeRequest = useRef(0);
  const restoring = useRef(Boolean(initialConversationId));

  useEffect(() => {
    const requestedId = initialConversationId;
    if (!requestedId) return;
    let active = true;
    getConversationHistory(requestedId).then((history) => {
      if (!active || activeRequest.current !== 0) return;
      setMessages(restoreConversationMessages(history.messages));
    }).catch((cause: unknown) => {
      if (active) setError(cause instanceof Error ? cause.message : '无法恢复对话。');
    }).finally(() => {
      if (!active) return;
      restoring.current = false;
      setIsRestoring(false);
    });
    return () => { active = false; };
  }, [initialConversationId]);

  const submit = useCallback(async (expression: string, onWorldConsequenceReady?: () => void) => {
    if (isResponding || restoring.current || !expression.trim()) return;
    const requestId = ++activeRequest.current;
    const activeConversationId = conversationId || createClientId();
    if (!conversationId) {
      setConversationId(activeConversationId);
      const url = new URL(window.location.href);
      url.searchParams.set('conversation_id', activeConversationId);
      window.history.replaceState({}, '', url);
    }
    setError(null);
    setIsResponding(true);
    setMessages((current) => [...current,
      { id: `${requestId}:user`, role: 'user', content: expression },
      { id: `${requestId}:assistant`, role: 'assistant', content: '' },
    ]);
    try {
      await streamMessage({
        conversationId: activeConversationId,
        message: expression,
        onWorldConsequenceReady: () => {
          if (activeRequest.current === requestId) onWorldConsequenceReady?.();
        },
        onChunk: (chunk) => {
          if (activeRequest.current !== requestId) return;
          setMessages((current) => appendAssistantChunk(current, `${requestId}:assistant`, chunk));
        },
      });
      const history = await getConversationHistory(activeConversationId);
      if (activeRequest.current === requestId) {
        setMessages(restoreConversationMessages(history.messages));
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '回复暂时无法送达。');
    } finally {
      if (activeRequest.current === requestId) setIsResponding(false);
    }
  }, [conversationId, isResponding]);

  return { conversationId, messages, isResponding, isRestoring, error, submit };
}
