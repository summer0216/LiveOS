'use client';

import { useRef, type ReactNode } from 'react';
import type { GroundedPlace } from './groundedPlace';
import WorldEmergence from './WorldEmergence';
import WorldConversation from './WorldConversation';
import { useVisibleViewport } from './useVisibleViewport';
import styles from './world-focus.module.css';

interface WorldFocusSurfaceProps {
  place: GroundedPlace;
  conversation: ReactNode;
  entry: ReactNode;
  animateAppearance: boolean;
  isResponding: boolean;
  conversationExpanded: boolean;
  onConversationExpandedChange: (expanded: boolean) => void;
}

export default function WorldFocusSurface({
  place,
  conversation,
  entry,
  animateAppearance,
  isResponding,
  conversationExpanded,
  onConversationExpandedChange,
}: WorldFocusSurfaceProps) {
  const surface = useRef<HTMLElement>(null);
  useVisibleViewport(surface);
  return (
    <section ref={surface} className={styles.surface} aria-label="生活世界" data-conversation-expanded={conversationExpanded}>
      <WorldEmergence place={place} animateAppearance={animateAppearance} />
      <WorldConversation
        context={place.name}
        isResponding={isResponding}
        expanded={conversationExpanded}
        onExpandedChange={onConversationExpandedChange}
        conversation={conversation}
        entry={entry}
      />
    </section>
  );
}
