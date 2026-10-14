import Image from 'next/image';
import styles from './Wordmark.module.css';

/** Use the delivered outlines unchanged, with a neutral backing for every surface. */
export default function Wordmark() {
  return (
    <span className={styles.wordmark}>
      <Image
        src="/brand/liveos-wordmark-deep-green.svg"
        alt="LiveOS"
        width={372.48}
        height={140}
        className={styles.image}
      />
    </span>
  );
}
