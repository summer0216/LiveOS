'use client';
import { ThumbsUp, ThumbsDown } from 'lucide-react';
import { useRef, useState } from 'react';
import type { MessageFeedback as Feedback } from '../../contracts/conversation';
import { setMessageFeedback } from '../../infrastructure/conversationApi';
import styles from './message-feedback.module.css';

export default function MessageFeedback({ conversationId, messageId, feedback }: {
  conversationId: string;
  messageId: string;
  feedback: Feedback | null;
}) {
  const [selected, setSelected] = useState(feedback);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const inFlight = useRef(false);

  async function choose(value: Feedback) {
    if (inFlight.current) return;
    inFlight.current = true;
    const previous = selected;
    const next = selected === value ? null : value;
    setSelected(next);
    setPending(true);
    setError('');
    try {
      const result = await setMessageFeedback(conversationId, messageId, next);
      setSelected(result.feedback);
    } catch {
      setSelected(previous);
      setError('评价未保存，请重试。');
    } finally {
      inFlight.current = false;
      setPending(false);
    }
  }

  return (
    <div className={styles.feedback} aria-label="回复评价" aria-busy={pending}>
      <div className={styles.buttons}>
        <button type="button" aria-label="赞同回复" aria-pressed={selected === 'POSITIVE'} disabled={pending} onClick={() => choose('POSITIVE')}>
          <ThumbsUp size={18} strokeWidth={1.7} />
        </button>
        <button type="button" aria-label="不赞同回复" aria-pressed={selected === 'NEGATIVE'} disabled={pending} onClick={() => choose('NEGATIVE')}>
          <ThumbsDown size={18} strokeWidth={1.7} />
        </button>
      </div>
      {error && <p className={styles.error} role="alert">{error}</p>}
    </div>
  );
}
