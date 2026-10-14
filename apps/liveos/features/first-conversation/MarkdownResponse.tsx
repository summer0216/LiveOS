import { createElement } from 'react';
import { inlineTokens, markdownBlocks } from './markdown';
import styles from './first-conversation.module.css';

function inline(text: string) {
  return inlineTokens(text).map((token, index) => {
    if (token.kind === 'text') return token.text;
    if (token.kind === 'link') return <a key={index} href={token.href} target="_blank" rel="noopener noreferrer">{token.text}</a>;
    return createElement(token.kind, { key: index }, token.text);
  });
}

/** Render plain structured text through React; raw HTML is never interpreted. */
export default function MarkdownResponse({ content }: { content: string }) {
  return (
    <div className={styles.markdown}>
      {markdownBlocks(content).map((block, index) => {
        if (block.kind === 'rule') return <hr key={index} />;
        if (block.kind === 'heading') return createElement(`h${Math.max(2, block.level)}`, { key: index }, inline(block.text));
        if (block.kind === 'code') return <pre key={index}><code>{block.text}</code></pre>;
        if (block.kind === 'quote') return <blockquote key={index}>{inline(block.text)}</blockquote>;
        if (block.kind === 'list') {
          const items = block.items.map((item, itemIndex) => <li key={itemIndex}>{inline(item)}</li>);
          return block.ordered ? <ol key={index} start={block.start}>{items}</ol> : <ul key={index}>{items}</ul>;
        }
        return <p key={index}>{inline(block.text)}</p>;
      })}
    </div>
  );
}
