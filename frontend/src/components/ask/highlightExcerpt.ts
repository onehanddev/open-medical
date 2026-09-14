import { decodeString } from 'micromark-util-decode-string'
import type { Root, Element, Text, RootContent } from 'hast'

/** Match the complete excerpt, allowing only whitespace differences. */
export function findExcerptRange(page: string, excerpt: string) {
    const target = excerpt.trim().replace(/\s+/g, ' ')
    if (!target) return null

    const starts: number[] = []
    const ends: number[] = []
    let normalized = ''
    for (const token of page.matchAll(/\s+|\S/g)) {
        normalized += /\s/.test(token[0]) ? ' ' : token[0]
        starts.push(token.index)
        ends.push(token.index + token[0].length)
    }
    const index = normalized.indexOf(target)
    if (index < 0) return null
    return { start: starts[index], end: ends[index + target.length - 1] }
}

/** Add marks to text nodes after Markdown parsing, preserving the full page tree. */
export function highlightExcerpt(page: string, excerpt: string) {
    const range = findExcerptRange(page, excerpt)
    return () => (tree: Root) => {
        if (!range) return
        function visit(parent: Root | Element) {
            parent.children = parent.children.flatMap((node): RootContent[] => {
                if (node.type === 'element') {
                    visit(node)
                    return [node]
                }
                if (node.type !== 'text') return [node]
                const start = node.position?.start.offset
                const end = node.position?.end.offset
                if (start === undefined || end === undefined || end <= range!.start || start >= range!.end) {
                    return [node]
                }
                // Decode prefixes just as Markdown decodes escapes and entities.
                const decodedLength = (offset: number) => decodeString(page.slice(start, offset))
                    .replace(/\r\n?/g, '\n').length
                const from = decodedLength(Math.max(start, range!.start))
                const to = decodedLength(Math.min(end, range!.end))
                const text = (value: string): Text => ({ type: 'text', value })
                return [
                    text(node.value.slice(0, from)),
                    {
                        type: 'element', tagName: 'mark',
                        properties: { className: ['source-match'] },
                        children: [text(node.value.slice(from, to))],
                    },
                    text(node.value.slice(to)),
                ]
            }) as typeof parent.children
        }
        visit(tree)
    }
}
