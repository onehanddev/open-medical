import { useEffect, useRef, useState } from "react"
import { FileTextIcon, Loader2Icon, XIcon } from "lucide-react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import rehypeRaw from "rehype-raw"
import { Button } from "../../../components/ui/button"
import { fetchSource, getRetrievalUrl } from "./citation_apis"
import { highlightExcerpt } from "./highlightExcerpt"
import type { ISources } from "./types"

function getDocKey(documentKey: string | undefined): string | undefined {
    if (!documentKey) return undefined
    const afterPdf = documentKey.split("pdf/")[1]
    if (!afterPdf) return undefined
    return afterPdf.split(".pdf")[0]
}

function getDocumentName(documentKey: string): string {
    return documentKey.replace(/^pdf\//i, "").replace(/\.pdf$/i, "")
}

// Module-level caches so repeat clicks across messages don't re-hit CloudFront.
const pageCache = new Map<string, string>()
const retrievalUrlCache = new Map<string, { baseUrl: string; signedQuery: string }>()

function decodeSupportedInlineHtml(markdown: string): string {
    return markdown.replace(/&lt;u&gt;/gi, "<u>").replace(/&lt;\/u&gt;/gi, "</u>")
}

function PageContent({ pageMd, excerpt }: { pageMd: string; excerpt: string }) {
    const markdown = decodeSupportedInlineHtml(pageMd)
    return (
        <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw, highlightExcerpt(markdown, excerpt)]}>
            {markdown}
        </ReactMarkdown>
    )
}

export default function SourceViewer({
    source,
    onClose,
    onPageChange,
}: {
    source: ISources
    onClose: () => void
    onPageChange: (pageNumber: number) => void
}) {
    const [content, setContent] = useState<string | null>(null)
    const [isLoading, setIsLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [retryCount, setRetryCount] = useState(0)
    const bodyRef = useRef<HTMLDivElement>(null)
    const sourceNumber = source.source_id.split("_")[1] ?? source.source_id
    const sourceMetadata = [source.chapter, source.section].filter(Boolean).join("\n\n")

    useEffect(() => {
        let cancelled = false
        async function load() {
            setIsLoading(true)
            setError(null)
            setContent(null)
            const docKey = getDocKey(source.document_key)
            if (!docKey) {
                setError("Missing document reference for this source.")
                setIsLoading(false)
                return
            }
            const cacheKey = `${docKey}::${source.page_num}`
            const cached = pageCache.get(cacheKey)
            if (cached !== undefined) {
                setContent(cached)
                setIsLoading(false)
                return
            }
            try {
                let retrievalUrl: { baseUrl: string; signedQuery: string } | undefined = retrievalUrlCache.get(docKey)
                if (!retrievalUrl) {
                    retrievalUrl = (await getRetrievalUrl(docKey)) as { baseUrl: string; signedQuery: string }
                    retrievalUrlCache.set(docKey, retrievalUrl)
                }
                const pageMd = await fetchSource(retrievalUrl.baseUrl, retrievalUrl.signedQuery, source.page_num)
                if (cancelled) return
                pageCache.set(cacheKey, pageMd)
                setContent(pageMd)
            } catch (err) {
                if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load source page.")
            } finally {
                if (!cancelled) setIsLoading(false)
            }
        }
        void load()
        return () => {
            cancelled = true
        }
    }, [source.document_key, source.page_num, retryCount])

    useEffect(() => {
        if (isLoading || error || !content) return
        const frame = requestAnimationFrame(() => {
            const body = bodyRef.current
            const highlights = body?.querySelectorAll<HTMLElement>(".source-page .source-match")
            if (!body || !highlights?.length) return
            const first = highlights[0].getBoundingClientRect()
            const last = highlights[highlights.length - 1].getBoundingClientRect()
            const top =
                body.scrollTop +
                (first.top + last.bottom) / 2 -
                body.getBoundingClientRect().top -
                body.clientTop -
                body.clientHeight / 2
            body.scrollTo({
                top: Math.max(0, top),
                behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth",
            })
        })
        return () => cancelAnimationFrame(frame)
    }, [content, isLoading, error, source.source_id, source.content])

    useEffect(() => {
        function handleKeyDown(event: KeyboardEvent) {
            if (event.key === "Escape") onClose()
        }
        document.addEventListener("keydown", handleKeyDown)
        const previousOverflow = document.body.style.overflow
        document.body.style.overflow = "hidden"
        return () => {
            document.removeEventListener("keydown", handleKeyDown)
            document.body.style.overflow = previousOverflow
        }
    }, [onClose])

    return (
        <div className="source-viewer-root">
            <div className="source-backdrop" onClick={onClose} aria-hidden="true" />
            <aside className="source-panel" role="dialog" aria-modal="true" aria-label={`Source ${sourceNumber}`}>
                <header className="source-panel-header">
                    <div className="source-panel-title">
                        <span className="source-badge">{sourceNumber}</span>
                        <div>
                            <p className="source-panel-heading">{getDocumentName(source.document_key) || `Source ${sourceNumber}`}</p>
                            <p className="source-panel-sub">
                                Source {sourceNumber} · {sourceMetadata && <ReactMarkdown>{sourceMetadata}</ReactMarkdown>}
                            </p>
                        </div>
                    </div>
                    <button type="button" className="source-close" onClick={onClose} aria-label="Close source viewer">
                        <XIcon aria-hidden="true" />
                    </button>
                </header>

                <nav className="source-page-nav" aria-label="Source page navigation">
                    <button type="button" onClick={() => onPageChange(source.page_num - 1)} disabled={isLoading || source.page_num <= 1}>
                        &lt; Page no. {source.page_num - 1}
                    </button>
                    <span>Page no. {source.page_num}</span>
                    <button type="button" onClick={() => onPageChange(source.page_num + 1)} disabled={isLoading}>
                        Page no. {source.page_num + 1} &gt;
                    </button>
                </nav>

                <div ref={bodyRef} className="source-panel-body">
                    {isLoading && (
                        <div className="source-state" role="status">
                            <Loader2Icon aria-hidden="true" className="animate-spin" />
                            <p>Loading page {source.page_num}…</p>
                        </div>
                    )}
                    {!isLoading && error && (
                        <div className="source-state source-error" role="alert">
                            <p>Couldn’t load this page.</p>
                            <span>{error}</span>
                            <Button type="button" className="ask-button" onClick={() => setRetryCount((c) => c + 1)}>
                                Retry
                            </Button>
                        </div>
                    )}
                    {!isLoading && !error && content && (
                        <div className="source-page">
                            <p className="source-page-label">
                                <FileTextIcon aria-hidden="true" />
                                Full page {source.page_num}
                            </p>
                            <PageContent pageMd={content} excerpt={source.content} />
                        </div>
                    )}
                </div>
            </aside>
        </div>
    )
}
