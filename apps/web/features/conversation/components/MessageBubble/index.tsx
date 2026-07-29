import type { ReactNode } from 'react';

interface MessageBubbleProps {
    role: 'user' | 'assistant';
    content: string;
}

export default function MessageBubble({
    role,
    content,
}: MessageBubbleProps) {
    const isUser = role === 'user';

    return (
        <article
            className={[
                'mb-8 flex items-start gap-3 sm:gap-4',
                isUser ? 'justify-end' : 'justify-start',
            ].join(' ')}
        >
            {!isUser && <AIAvatar />}

            <div
                className={[
                    'min-w-0 rounded-2xl border px-5 py-3.5 text-[15px] leading-7 sm:px-6 sm:py-4',
                    isUser
                        ? 'max-w-[min(76%,680px)] border-blue-500/30 bg-blue-500/10 text-slate-200'
                        : 'max-w-[min(84%,760px)] border-white/[0.08] bg-[#0b1020] text-slate-300',
                ].join(' ')}
            >
                {isUser ? (
                    <p className="whitespace-pre-wrap break-words">
                        {content}
                    </p>
                ) : (
                    <MarkdownContent content={content} />
                )}
            </div>

            {isUser && (
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-violet-500 text-sm font-medium text-white">
                    我
                </span>
            )}
        </article>
    );
}

function MarkdownContent({ content }: { content: string }) {
    const lines = content.replace(/\r\n?/g, '\n').split('\n');
    const blocks: ReactNode[] = [];
    let lineIndex = 0;
    let blockIndex = 0;

    while (lineIndex < lines.length) {
        const line = lines[lineIndex];

        if (!line.trim()) {
            lineIndex += 1;
            continue;
        }

        const codeFence = line.match(/^```([\w-]*)\s*$/);

        if (codeFence) {
            const codeLines: string[] = [];
            const language = codeFence[1];
            lineIndex += 1;

            while (
                lineIndex < lines.length &&
                !/^```\s*$/.test(lines[lineIndex])
            ) {
                codeLines.push(lines[lineIndex]);
                lineIndex += 1;
            }

            if (lineIndex < lines.length) {
                lineIndex += 1;
            }

            blocks.push(
                <pre
                    key={`code-${blockIndex}`}
                    className="my-4 overflow-x-auto rounded-xl border border-white/10 bg-black/30 p-4 font-mono text-[13px] leading-6 text-slate-300 first:mt-0 last:mb-0"
                >
                    <code
                        className={
                            language
                                ? `language-${language}`
                                : undefined
                        }
                    >
                        {codeLines.join('\n')}
                    </code>
                </pre>,
            );
            blockIndex += 1;
            continue;
        }

        const heading = line.match(/^(#{1,6})\s+(.+)$/);

        if (heading) {
            blocks.push(
                renderHeading(
                    heading[1].length,
                    heading[2],
                    blockIndex,
                ),
            );
            blockIndex += 1;
            lineIndex += 1;
            continue;
        }

        if (/^\s*[-+*]\s+/.test(line)) {
            const items: string[] = [];

            while (
                lineIndex < lines.length &&
                /^\s*[-+*]\s+/.test(lines[lineIndex])
            ) {
                items.push(
                    lines[lineIndex].replace(
                        /^\s*[-+*]\s+/,
                        '',
                    ),
                );
                lineIndex += 1;
            }

            blocks.push(
                <ul
                    key={`unordered-${blockIndex}`}
                    className="my-3 list-disc space-y-1 pl-5 leading-7 marker:text-blue-400 first:mt-0 last:mb-0"
                >
                    {items.map((item, itemIndex) => (
                        <li key={`${item}-${itemIndex}`}>
                            {renderInline(item)}
                        </li>
                    ))}
                </ul>,
            );
            blockIndex += 1;
            continue;
        }

        if (/^\s*\d+\.\s+/.test(line)) {
            const items: string[] = [];

            while (
                lineIndex < lines.length &&
                /^\s*\d+\.\s+/.test(lines[lineIndex])
            ) {
                items.push(
                    lines[lineIndex].replace(
                        /^\s*\d+\.\s+/,
                        '',
                    ),
                );
                lineIndex += 1;
            }

            blocks.push(
                <ol
                    key={`ordered-${blockIndex}`}
                    className="my-3 list-decimal space-y-1 pl-5 leading-7 marker:text-blue-400 first:mt-0 last:mb-0"
                >
                    {items.map((item, itemIndex) => (
                        <li key={`${item}-${itemIndex}`}>
                            {renderInline(item)}
                        </li>
                    ))}
                </ol>,
            );
            blockIndex += 1;
            continue;
        }

        const paragraphLines = [line.trim()];
        lineIndex += 1;

        while (
            lineIndex < lines.length &&
            lines[lineIndex].trim() &&
            !isBlockStart(lines[lineIndex])
        ) {
            paragraphLines.push(lines[lineIndex].trim());
            lineIndex += 1;
        }

        blocks.push(
            <p
                key={`paragraph-${blockIndex}`}
                className="my-3 break-words leading-7 first:mt-0 last:mb-0"
            >
                {renderInline(paragraphLines.join(' '))}
            </p>,
        );
        blockIndex += 1;
    }

    return <div>{blocks}</div>;
}

function isBlockStart(line: string): boolean {
    return (
        /^```/.test(line) ||
        /^#{1,6}\s+/.test(line) ||
        /^\s*[-+*]\s+/.test(line) ||
        /^\s*\d+\.\s+/.test(line)
    );
}

function renderHeading(
    level: number,
    content: string,
    key: number,
): ReactNode {
    const children = renderInline(content);
    const className =
        'mb-2 mt-5 font-semibold leading-snug tracking-tight text-slate-100 first:mt-0';

    switch (level) {
        case 1:
            return (
                <h1
                    key={`heading-${key}`}
                    className={`${className} text-xl`}
                >
                    {children}
                </h1>
            );
        case 2:
            return (
                <h2
                    key={`heading-${key}`}
                    className={`${className} text-lg`}
                >
                    {children}
                </h2>
            );
        case 3:
            return (
                <h3
                    key={`heading-${key}`}
                    className={`${className} text-base`}
                >
                    {children}
                </h3>
            );
        default:
            return (
                <h4
                    key={`heading-${key}`}
                    className={`${className} text-base`}
                >
                    {children}
                </h4>
            );
    }
}

function renderInline(content: string): ReactNode[] {
    const tokenPattern =
        /(`[^`\n]+`|\*\*[^*\n]+\*\*|__[^_\n]+__|\*[^*\n]+\*|_[^_\n]+_)/g;
    const nodes: ReactNode[] = [];
    let cursor = 0;
    let tokenIndex = 0;

    for (const match of content.matchAll(tokenPattern)) {
        const matchIndex = match.index;

        if (matchIndex > cursor) {
            nodes.push(content.slice(cursor, matchIndex));
        }

        const token = match[0];

        if (token.startsWith('`')) {
            nodes.push(
                <code
                    key={`inline-${tokenIndex}`}
                    className="rounded bg-white/10 px-1.5 py-0.5 font-mono text-[0.88em] text-blue-200"
                >
                    {token.slice(1, -1)}
                </code>,
            );
        } else if (
            token.startsWith('**') ||
            token.startsWith('__')
        ) {
            nodes.push(
                <strong
                    key={`inline-${tokenIndex}`}
                    className="font-semibold text-slate-100"
                >
                    {renderInline(token.slice(2, -2))}
                </strong>,
            );
        } else {
            nodes.push(
                <em
                    key={`inline-${tokenIndex}`}
                    className="italic text-slate-200"
                >
                    {renderInline(token.slice(1, -1))}
                </em>,
            );
        }

        cursor = matchIndex + token.length;
        tokenIndex += 1;
    }

    if (cursor < content.length) {
        nodes.push(content.slice(cursor));
    }

    return nodes;
}

export function AIAvatar() {
    return (
        <span
            aria-label="LiveOS"
            className="h-10 w-10 shrink-0 rounded-full bg-[radial-gradient(circle_at_35%_30%,#79b9ff_0,#4d89ca_42%,#38a77c_100%)] shadow-[0_0_20px_rgba(70,174,161,0.34)]"
        />
    );
}
