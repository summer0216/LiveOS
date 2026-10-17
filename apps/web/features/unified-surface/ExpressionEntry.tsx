'use client';

import { useRef, useState, type KeyboardEvent } from 'react';
import styles from './UnifiedSurface.module.css';

interface ExpressionEntryProps {
  disabled: boolean;
  onSubmit: (expression: string) => Promise<void>;
}

export default function ExpressionEntry({ disabled, onSubmit }: ExpressionEntryProps) {
  const [value, setValue] = useState('');
  const submitting = useRef(false);
  const submit = async () => {
    const expression = value.trim();
    if (!expression || disabled || submitting.current) return;
    submitting.current = true;
    setValue('');
    try {
      await onSubmit(expression);
    } finally {
      submitting.current = false;
    }
  };
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== 'Enter' || event.shiftKey || event.nativeEvent.isComposing) return;
    event.preventDefault();
    void submit();
  };
  return (
    <form className={styles.expression} onSubmit={(event) => { event.preventDefault(); void submit(); }}>
      <textarea
        rows={2}
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={onKeyDown}
        readOnly={disabled}
        aria-busy={disabled}
        aria-label="告诉 LiveOS 一件关于生活的事"
        placeholder="从你想说的开始…"
      />
      <button type="submit" disabled={disabled || !value.trim()} aria-label="提交表达">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 19V5m-5 5 5-5 5 5" /></svg>
      </button>
    </form>
  );
}
