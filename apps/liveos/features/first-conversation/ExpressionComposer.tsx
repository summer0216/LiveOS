'use client';

import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react';
import styles from './first-conversation.module.css';

export default function ExpressionComposer({ onSubmit, disabled }: {
  onSubmit: (expression: string) => Promise<void>;
  disabled: boolean;
}) {
  const [value, setValue] = useState('');
  const input = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    if (!input.current) return;
    input.current.style.height = 'auto';
    input.current.style.height = `${Math.min(input.current.scrollHeight, 156)}px`;
  }, [value]);
  const send = (event: FormEvent) => {
    event.preventDefault();
    const expression = value.trim();
    if (!expression || disabled) return;
    setValue('');
    void onSubmit(expression);
  };
  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  };

  return (
    <form className={styles.composer} onSubmit={send} aria-busy={disabled}>
      <label className={styles.srOnly} htmlFor="expression">写下你正在想的事</label>
      <textarea
        ref={input}
        id="expression"
        rows={1}
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="写下你正在想的事…"
      />
      <button type="submit" aria-label="发送" disabled={disabled || !value.trim()}>↑</button>
    </form>
  );
}
