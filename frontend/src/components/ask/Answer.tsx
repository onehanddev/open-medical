import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { cn } from "cn"
import type { ISources } from "./types"

function CitationButton({
    sourceNumber,
    onClick,
    isActive,
}: {
    sourceNumber: string
    onClick: () => void
    isActive?: boolean
}) {
    return (
        <button
            onClick={onClick}
            aria-label={`Open source ${sourceNumber}`}
            className={cn("citation-btn", isActive && "citation-btn-active")}
        >
            {sourceNumber}
        </button>
    )
}

export default function Answer({
    answer,
    sources,
    onSourceClick,
    activeSourceId,
}: {
    answer: string
    sources: ISources[]
    onSourceClick: (source: ISources) => void
    activeSourceId?: string | null
}) {
    const markdown = answer.replace(
        /(?:\[|［)?SOURCE_(\d+)(?:\]|］)?/g,
        (_, sourceNumber) => `[SOURCE_${sourceNumber}](#source-${sourceNumber})`,
    )

    const openCitation = (sourceNumber: string) => {
        const source = sources.find((s) => s.source_id.split("_")[1] === sourceNumber)
        if (source) onSourceClick(source)
    }

    return (
        <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
                a: ({ href, children }) => {
                    if (href?.startsWith("#source-")) {
                        const sourceNumber = href.replace("#source-", "")
                        const source = sources.find((s) => s.source_id.split("_")[1] === sourceNumber)
                        return (
                            <CitationButton
                                sourceNumber={sourceNumber}
                                isActive={!!source && source.source_id === activeSourceId}
                                onClick={() => openCitation(sourceNumber)}
                            />
                        )
                    }
                    return <a href={href}>{children}</a>
                },
                table: ({ children }) => (
                    <div className="ask-answer-table-scroll" tabIndex={0}>
                        <table>{children}</table>
                    </div>
                ),
            }}
        >
            {markdown}
        </ReactMarkdown>
    )
}
