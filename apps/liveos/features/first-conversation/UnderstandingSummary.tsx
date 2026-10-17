'use client';

import { useEffect, useState } from 'react';
import { getLivingProfile, type LivingProfile } from '@/services/profile';
import { understandingRows } from './understanding';
import styles from './first-conversation.module.css';

export default function UnderstandingSummary({ conversationId, responseId }: {
  conversationId: string;
  responseId: string;
}) {
  const [result, setResult] = useState<{
    conversationId: string; responseId: string; profile: LivingProfile | null; failed: boolean;
  } | null>(null);
  useEffect(() => {
    let active = true;
    getLivingProfile(conversationId).then((profile) => {
      if (active) setResult({ conversationId, responseId, profile, failed: false });
    }).catch(() => {
      if (active) setResult({ conversationId, responseId, profile: null, failed: true });
    });
    return () => { active = false; };
  }, [conversationId, responseId]);

  if (result?.conversationId !== conversationId || result.responseId !== responseId) return null;
  if (result.failed) return <p role="status">关键信息暂时无法读取。</p>;
  if (!result.profile || result.profile.conversation_id !== conversationId) return null;
  return (
    <section className={styles.understanding} aria-label="我为你梳理的关键信息">
      <h2>我为你梳理的关键信息</h2>
      <dl>
        {understandingRows(result.profile).map((row) => (
          <div key={row.label}>
            <dt>{row.label}</dt>
            <dd>{row.value}{row.status !== '未明确' && <small>{row.status}</small>}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
