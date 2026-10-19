'use client';

import { useEffect, useRef, useState, type PointerEvent, type ReactNode } from 'react';
import { ChevronUp, MessageSquare, X } from 'lucide-react';
import styles from './world-focus.module.css';

interface WorldConversationProps {
  context: string | null;
  isResponding: boolean;
  expanded: boolean;
  onExpandedChange: (expanded: boolean) => void;
  conversation: ReactNode;
  entry: ReactNode;
}

export default function WorldConversation({
  context, isResponding, expanded, onExpandedChange, conversation, entry,
}: WorldConversationProps) {
  const [fullScreen, setFullScreen] = useState(false);
  const dock = useRef<HTMLButtonElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  const startY = useRef<number | null>(null);
  const swiped = useRef(false);
  const close = () => {
    setFullScreen(false);
    onExpandedChange(false);
  };
  useEffect(() => {
    if (expanded) closeButton.current?.focus();
    else dock.current?.focus();
  }, [expanded]);
  const startSwipe = (event: PointerEvent<HTMLElement>) => {
    if (window.matchMedia('(min-width: 1024px)').matches) return;
    startY.current = event.clientY;
    swiped.current = false;
    event.currentTarget.setPointerCapture(event.pointerId);
  };
  const finishSwipe = (event: PointerEvent<HTMLElement>) => {
    if (startY.current === null) return;
    const distance = event.clientY - startY.current;
    startY.current = null;
    swiped.current = Math.abs(distance) > 40;
    if (distance < -40) {
      if (expanded) setFullScreen(true);
      else onExpandedChange(true);
    } else if (distance > 40 && expanded) {
      if (fullScreen) setFullScreen(false);
      else close();
    }
  };

  return (
    <div className={styles.conversationAccess} data-full-screen={expanded && fullScreen}>
      <button
        ref={dock}
        type="button"
        className={styles.dock}
        hidden={expanded}
        aria-label="展开对话"
        aria-expanded={expanded}
        aria-controls="world-conversation"
        onClick={() => onExpandedChange(true)}
        onPointerDown={startSwipe}
        onPointerUp={finishSwipe}
        onPointerCancel={() => { startY.current = null; }}
      >
        <MessageSquare size={20} aria-hidden="true" />
        <span className={styles.dockTitle}>对话</span>
        <span className={styles.context}>{isResponding ? '正在回应' : context}</span>
        <ChevronUp className={styles.expandIcon} size={20} aria-hidden="true" />
      </button>
      <section
        id="world-conversation"
        className={styles.conversationLayer}
        hidden={!expanded}
        aria-label="当前会话"
        onKeyDown={(event) => {
          if (event.key === 'Escape') { event.stopPropagation(); close(); }
        }}
      >
        <button
          type="button"
          className={styles.handle}
          aria-label={fullScreen ? '下滑返回半屏对话' : '上滑展开全屏对话，下滑收起'}
          onPointerDown={startSwipe}
          onPointerUp={finishSwipe}
          onPointerCancel={() => { startY.current = null; }}
          onClick={() => { if (!swiped.current) setFullScreen(!fullScreen); }}
          onKeyDown={(event) => {
            if (event.key === 'ArrowUp') { event.preventDefault(); setFullScreen(true); }
            if (event.key === 'ArrowDown') {
              event.preventDefault();
              if (fullScreen) setFullScreen(false);
              else close();
            }
          }}
        ><span /></button>
        <header className={styles.panelHeader}>
          <div>
            <h2>对话</h2>
            <p>{context ? `${context} · 当前会话` : '当前会话'}</p>
          </div>
          <button ref={closeButton} type="button" aria-label="收起对话" onClick={close}>
            <X size={20} aria-hidden="true" />
          </button>
        </header>
        <div className={styles.conversationBody}>{conversation}</div>
        <div className={styles.composer}>{entry}</div>
      </section>
    </div>
  );
}
