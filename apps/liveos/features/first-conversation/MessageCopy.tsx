'use client';

import { Check, Copy } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import actionStyles from './message-feedback.module.css';
import styles from './first-conversation.module.css';

export default function MessageCopy({ content }: { content: string }) {
  const [status, setStatus] = useState<'copied' | 'error' | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      clearTimeout(timer.current);
    };
  }, []);

  async function copy() {
    try {
      await navigator.clipboard.writeText(content);
      if (!mounted.current) return;
      clearTimeout(timer.current);
      setStatus('copied');
      timer.current = setTimeout(() => setStatus(null), 2000);
    } catch {
      if (!mounted.current) return;
      clearTimeout(timer.current);
      setStatus('error');
    }
  }

  return (
    <span className={actionStyles.buttons}>
      <button type="button" aria-label={status === 'copied' ? '已复制' : '复制回复'} onClick={copy}>
        {status === 'copied' ? <Check size={18} strokeWidth={1.7} /> : <Copy size={18} strokeWidth={1.7} />}
      </button>
      <span className={styles.srOnly} role="status">
        {status === 'copied' ? '已复制' : status === 'error' ? '复制失败，请重试。' : ''}
      </span>
    </span>
  );
}
