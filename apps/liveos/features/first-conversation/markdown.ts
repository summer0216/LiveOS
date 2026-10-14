export type MarkdownBlock =
  | { kind: 'rule' }
  | { kind: 'paragraph' | 'quote' | 'code'; text: string }
  | { kind: 'heading'; text: string; level: number }
  | { kind: 'list'; ordered: boolean; start: number; items: string[] };

export function markdownBlocks(content: string): MarkdownBlock[] {
  const lines = content.replaceAll('\r\n', '\n').split('\n');
  const blocks: MarkdownBlock[] = [];
  for (let index = 0; index < lines.length;) {
    const line = lines[index];
    if (!line.trim()) { index++; continue; }
    if (/^\s{0,3}(?:-{3,}|\*{3,}|_{3,})\s*$/.test(line)) {
      blocks.push({ kind: 'rule' }); index++; continue;
    }
    if (/^\s*```/.test(line)) {
      const code: string[] = [];
      index++;
      while (index < lines.length && !/^\s*```/.test(lines[index])) code.push(lines[index++]);
      if (index < lines.length) index++;
      blocks.push({ kind: 'code', text: code.join('\n') });
      continue;
    }
    const heading = line.match(/^\s{0,3}(#{1,6})\s+(.+?)\s*#*$/);
    if (heading) {
      blocks.push({ kind: 'heading', level: heading[1].length, text: heading[2] }); index++; continue;
    }
    if (/^\s*>/.test(line)) {
      const quote: string[] = [];
      while (index < lines.length && /^\s*>/.test(lines[index])) quote.push(lines[index++].replace(/^\s*>\s?/, ''));
      blocks.push({ kind: 'quote', text: quote.join('\n') }); continue;
    }
    const listItem = /^\s*(?:([-+*])|([0-9]+)[.)])\s+(.+)$/;
    const first = line.match(listItem);
    if (first) {
      const ordered = Boolean(first[2]);
      const items: string[] = [];
      while (index < lines.length) {
        const item = lines[index].match(listItem);
        if (!item || Boolean(item[2]) !== ordered) break;
        items.push(item[3]); index++;
      }
      blocks.push({ kind: 'list', ordered, start: Number(first[2] ?? 1), items }); continue;
    }
    const paragraph = [line]; index++;
    while (index < lines.length && lines[index].trim()
      && !/^\s*(?:#{1,6}\s|>|```|[-+*]\s|[0-9]+[.)]\s|[-*_]{3,}\s*$)/.test(lines[index])) paragraph.push(lines[index++]);
    blocks.push({ kind: 'paragraph', text: paragraph.join('\n') });
  }
  return blocks;
}

export function safeMarkdownHref(href: string): string | null {
  if (/^https?:\/\/[^\s]+$/i.test(href)) return href;
  if (/^\/(?!\/)[^\s]*$/.test(href)) return href;
  return null;
}

export function inlineTokens(text: string) {
  const pattern = /(\*\*([^*]+)\*\*|__([^_]+)__|`([^`]+)`|\*([^*]+)\*|_([^_]+)_|\[([^\]]+)\]\(([^\s)]+)\))/g;
  const tokens: { kind: 'text' | 'strong' | 'em' | 'code' | 'link'; text: string; href?: string }[] = [];
  let offset = 0;
  for (const match of text.matchAll(pattern)) {
    if (match.index > offset) tokens.push({ kind: 'text', text: text.slice(offset, match.index) });
    const href = match[8] ? safeMarkdownHref(match[8]) : null;
    tokens.push(match[2] || match[3] ? { kind: 'strong', text: match[2] ?? match[3] }
      : match[4] ? { kind: 'code', text: match[4] }
      : match[5] || match[6] ? { kind: 'em', text: match[5] ?? match[6] }
      : href ? { kind: 'link', text: match[7], href }
      : { kind: 'text', text: match[7] });
    offset = match.index + match[0].length;
  }
  if (offset < text.length) tokens.push({ kind: 'text', text: text.slice(offset) });
  return tokens;
}
