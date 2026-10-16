import Image from 'next/image';
import type { PresentedMessage } from '../../contracts/conversation';
import styles from './first-conversation.module.css';

/** Owns identity rendering; the message unit owns placement beside or above content. */
export default function ConversationIdentity({ role }: { role: PresentedMessage['role'] }) {
  return (
    <span className={styles.speaker}>
      {role === 'user' ? '你' : (
        <Image
          src="/brand/liveos-wordmark-deep-green.svg"
          alt="LiveOS"
          width={372.48}
          height={140}
          className={styles.identityWordmark}
        />
      )}
    </span>
  );
}
