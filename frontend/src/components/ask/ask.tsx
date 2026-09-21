import { useEffect, useRef, useState, type FormEvent } from "react"
import {
    ArrowUpIcon,
    CheckIcon,
    BookOpenIcon,
    ChevronLeftIcon,
    ChevronRightIcon,
    FileTextIcon,
    GraduationCapIcon,
    Loader2Icon,
    ShieldAlertIcon,
    SparklesIcon,
    StethoscopeIcon,
    XIcon,
} from "lucide-react"
import { Button } from "../../../components/ui/button"
import { cn } from "cn"
import "./ask.css"
import { API_URL } from '@/src/getEnv';
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { highlightExcerpt } from "./highlightExcerpt"
import {getRetrievalUrl, fetchSource} from "./citation_apis"
import { prefilled_questions } from "../../../static/questions"


const MAX_QUESTION_LENGTH = 1000

const suggestionIcons = [StethoscopeIcon, GraduationCapIcon, FileTextIcon, BookOpenIcon]

interface ISources {
    source_id: string
    page_num: number,
    chapter: string | null,
    section: string | null,
    content: string,
    document_key: string

}

interface IAnswer {
    answer: string;
    sources: ISources[]
}

function CitationButton({
  sourceNumber,
  onClick,
  isActive,
}: {
  sourceNumber: string;
  onClick: () => void;
  isActive?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      aria-label={`Open source ${sourceNumber}`}
      className={cn("citation-btn", isActive && "citation-btn-active")}
    >
      {sourceNumber}
    </button>
  );
}


function Answer({
    answer,
    sources,
    onSourceClick,
    activeSourceId,
}: IAnswer & {
    onSourceClick: (source: ISources) => void
    activeSourceId?: string | null
}) {
    const markdown = answer.replace(
        /(?:\[|［)?SOURCE_(\d+)(?:\]|］)?/g,
        (_, sourceNumber) => `[SOURCE_${sourceNumber}](#source-${sourceNumber})`
    )

    const openCitation = (sourceNumber: string) => {
        const source = sources.find(
            source => source.source_id.split("_")[1] === sourceNumber
        )

        if (source) {
            onSourceClick(source)
        }
    }

    return (
        <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
                a: ({ href, children }) => {
                    if (href?.startsWith("#source-")) {
                        const sourceNumber = href.replace("#source-", "")
                        const source = sources.find(
                            s => s.source_id.split("_")[1] === sourceNumber
                        )

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
            }}
        >
            {markdown}
        </ReactMarkdown>
    )
}

function Composer({
    value,
    onChange,
    onSubmit,
    isThinking,
    autoFocus = false,
}: {
    value: string
    onChange: (next: string) => void
    onSubmit: (question: string) => Promise<void>
    isThinking: boolean
    autoFocus?: boolean
}) {
    const textareaRef = useRef<HTMLTextAreaElement>(null)

    useEffect(() => {
        const el = textareaRef.current
        if (!el) return
        el.style.height = "auto"
        el.style.height = `${Math.min(el.scrollHeight, 200)}px`
    }, [value])

    useEffect(() => {
        if (autoFocus) textareaRef.current?.focus()
    }, [autoFocus])

    function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
        if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
            event.preventDefault()
            event.currentTarget.form?.requestSubmit()
        }
    }

    async function handleSubmit(event: FormEvent) {
        event.preventDefault()

        if (!value.trim() || isThinking) return
        await onSubmit(value.trim())
    }

    const canAsk = value.trim().length > 0 && !isThinking

    return (
        <form onSubmit={handleSubmit} className="ask-composer" aria-label="Ask a medical question" aria-busy={isThinking}>
            <label className="sr-only" htmlFor="ask-input">
                Ask any question from your medical books
            </label>
            <div className="ask-composer-box">
                <div className="ask-composer-top">
                    <SparklesIcon aria-hidden="true" className="ask-sparkle" />
                    <span className="ask-scope">Global · Indian MBBS curriculum</span>
                    <span className="ask-scope-dot" aria-hidden="true" />
                    <span className="ask-scope-muted">Cited answers</span>
                </div>
                <textarea
                    ref={textareaRef}
                    id="ask-input"
                    value={value}
                    disabled={isThinking}
                    onChange={(event) => onChange(event.target.value.slice(0, MAX_QUESTION_LENGTH))}
                    onKeyDown={handleKeyDown}
                    placeholder="Ask anything — e.g. “First-line treatment of hypertension in pregnancy?”"
                    rows={3}
                    maxLength={MAX_QUESTION_LENGTH}
                    aria-describedby="ask-hint"
                    className="ask-textarea"
                />
                <div className="ask-composer-footer">
                    <p id="ask-hint" className="ask-hint">
                        Enter to ask · Shift + Enter for a new line
                    </p>
                    <div className="ask-footer-actions">
                        <span className={cn("ask-count", value.length >= MAX_QUESTION_LENGTH && "ask-count-full")}>
                            {value.length}/{MAX_QUESTION_LENGTH}
                        </span>
                        <Button
                            type="submit"
                            disabled={!canAsk}
                            className="ask-button"
                            aria-label={isThinking ? "Searching your books" : "Ask"}
                        >
                            {isThinking ? (
                                <Loader2Icon aria-hidden="true" className="animate-spin" />
                            ) : (
                                <ArrowUpIcon aria-hidden="true" />
                            )}
                            {isThinking ? "Searching…" : "Ask"}
                        </Button>
                    </div>
                </div>
            </div>
        </form>
    )
}

interface IRetrievalUrl {
    baseUrl: string
    signedQuery: string
}

function getDocKey(documentKey: string | undefined): string | undefined {
    if (!documentKey) return undefined
    const afterPdf = documentKey.split("pdf/")[1]
    if (!afterPdf) return undefined
    return afterPdf.split(".pdf")[0]
}

function getSourceNumber(source: ISources): string {
    return source.source_id.split("_")[1] ?? source.source_id
}

function PageContent({ pageMd, excerpt }: { pageMd: string; excerpt: string }) {
    return (
        <ReactMarkdown rehypePlugins={[highlightExcerpt(pageMd, excerpt)]}>
            {pageMd}
        </ReactMarkdown>
    )
}

function SourceViewer({
    source,
    content,
    isLoading,
    error,
    onClose,
    onRetry,
}: {
    source: ISources
    content: string | null
    isLoading: boolean
    error: string | null
    onClose: () => void
    onRetry: () => void
}) {
    const sourceNumber = getSourceNumber(source)
    const bodyRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        if (isLoading || error || !content) return

        const frame = requestAnimationFrame(() => {
            const body = bodyRef.current
            const highlights = body?.querySelectorAll<HTMLElement>('.source-page .source-match')
            if (!body || !highlights?.length) return

            // A chunk can span multiple marks across Markdown elements.
            const first = highlights[0].getBoundingClientRect()
            const last = highlights[highlights.length - 1].getBoundingClientRect()
            const excerptCenter = (first.top + last.bottom) / 2
            const top = body.scrollTop + excerptCenter
                - body.getBoundingClientRect().top - body.clientTop - body.clientHeight / 2
            body.scrollTo({
                top: Math.max(0, top),
                behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches
                    ? 'instant' : 'smooth',
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
            <aside
                className="source-panel"
                role="dialog"
                aria-modal="true"
                aria-label={`Source ${sourceNumber}`}
            >
                <header className="source-panel-header">
                    <div className="source-panel-title">
                        <span className="source-badge">{sourceNumber}</span>
                        <div>
                            <p className="source-panel-heading">Source {sourceNumber}</p>
                            <p className="source-panel-sub">
                                Page {source.page_num}
                                {source.chapter ? ` · ${source.chapter}` : ""}
                                {source.section ? ` · ${source.section}` : ""}
                            </p>
                        </div>
                    </div>
                    <button
                        type="button"
                        className="source-close"
                        onClick={onClose}
                        aria-label="Close source viewer"
                    >
                        <XIcon aria-hidden="true" />
                    </button>
                </header>

                <div ref={bodyRef} className="source-panel-body">
                    <figure className="source-excerpt">
                        <figcaption>Cited excerpt</figcaption>
                        <blockquote>{source.content}</blockquote>
                    </figure>

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
                            <Button type="button" className="ask-button" onClick={onRetry}>
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

const Ask = () => {
    const [answerResponse, setAnswerResponse] = useState<IAnswer>();
    const [draft, setDraft] = useState("");
    const [isThinking, setIsThinking] = useState(false);
    const [askError, setAskError] = useState<string | null>(null);
    const [answeredQuestion, setAnsweredQuestion] = useState("");
    const [suggestionIndex, setSuggestionIndex] = useState(0);
    const requestPending = useRef(false);
    const suggestionQuestion = prefilled_questions[suggestionIndex];
    const SuggestionIcon = suggestionIcons[suggestionIndex];

    function shiftSuggestion(direction: number) {
        setSuggestionIndex((current) =>
            (current + direction + prefilled_questions.length) % prefilled_questions.length
        )
    }

    async function askQuestion(question: string) {
        if (requestPending.current) return
        requestPending.current = true
        setIsThinking(true)
        setAskError(null)
        setAnswerResponse(undefined)
        handleCloseViewer()
        try {
            const response = await fetch(`${API_URL}/ask/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: question }),
            })
            if (!response.ok) throw new Error('Couldn’t get an answer. Please try again.')
            const answer: IAnswer = await response.json()
            if (typeof answer?.answer !== 'string' || !Array.isArray(answer.sources)) {
                throw new Error('The answer could not be read. Please try again.')
            }
            setAnsweredQuestion(question)
            setAnswerResponse(answer)
        } catch {
            setAskError('Couldn’t get an answer. Your question is saved above—please try again.')
        } finally {
            requestPending.current = false
            setIsThinking(false)
        }
    }

    const [viewerSource, setViewerSource] = useState<ISources | null>(null);
    const [viewerContent, setViewerContent] = useState<string | null>(null);
    const [viewerLoading, setViewerLoading] = useState(false);
    const [viewerError, setViewerError] = useState<string | null>(null);
    // Cache per document + page so repeat clicks don't re-hit CloudFront.
    const pageCache = useRef(new Map<string, string>());
    const retrievalUrlCache = useRef(new Map<string, IRetrievalUrl>());

    async function loadSourcePage(source: ISources) {
        const docKey = getDocKey(source.document_key)
        if (!docKey) {
            setViewerError("Missing document reference for this source.")
            return
        }
        const cacheKey = `${docKey}::${source.page_num}`
        const cached = pageCache.current.get(cacheKey)
        if (cached !== undefined) {
            setViewerContent(cached)
            setViewerLoading(false)
            return
        }
        setViewerLoading(true)
        setViewerError(null)
        try {
            let retrievalUrl = retrievalUrlCache.current.get(docKey)
            if (!retrievalUrl) {
                const fetched: IRetrievalUrl = await getRetrievalUrl(docKey)
                retrievalUrlCache.current.set(docKey, fetched)
                retrievalUrl = fetched
            }
            const pageMd = await fetchSource(
                retrievalUrl.baseUrl,
                retrievalUrl.signedQuery,
                source.page_num
            )
            pageCache.current.set(cacheKey, pageMd)
            setViewerContent(pageMd)
        } catch (err) {
            setViewerError(err instanceof Error ? err.message : "Failed to load source page.")
            setViewerContent(null)
        } finally {
            setViewerLoading(false)
        }
    }

    function handleSourceClick(source: ISources) {
        setViewerSource(source)
        setViewerContent(null)
        setViewerError(null)
        setViewerLoading(true)
        void loadSourcePage(source)
    }

    function handleCloseViewer() {
        setViewerSource(null)
        setViewerContent(null)
        setViewerError(null)
        setViewerLoading(false)
    }

    function handleRetryViewer() {
        if (viewerSource) void loadSourcePage(viewerSource)
    }


    return (
        <div className="ask-page">
            <section className="ask-hero" aria-labelledby="ask-title">
                <div className="eyebrow">
                    <span /> Cited answers for Indian doctors & students
                </div>
                <h1 id="ask-title">
                    Ask anything.
                    <br />
                    <span>Answer with citations.</span>
                </h1>
                <p className="ask-hero-sub">
                    Search across your uploaded medical and curriculum books. Every answer points back to the
                    exact book, chapter, and page.
                </p>

                <div className="ask-suggestions" aria-label="Try an example question">
                    <button
                        type="button"
                        className="ask-suggestion-nav"
                        onClick={() => shiftSuggestion(-1)}
                        disabled={isThinking}
                        aria-label="Previous example question"
                    >
                        <ChevronLeftIcon aria-hidden="true" />
                    </button>
                    <button
                        type="button"
                        className="ask-suggestion"
                        disabled={isThinking}
                        onClick={() => setDraft(suggestionQuestion)}
                    >
                        <SuggestionIcon aria-hidden="true" />
                        <span>{suggestionQuestion}</span>
                    </button>
                    <button
                        type="button"
                        className="ask-suggestion-nav"
                        onClick={() => shiftSuggestion(1)}
                        disabled={isThinking}
                        aria-label="Next example question"
                    >
                        <ChevronRightIcon aria-hidden="true" />
                    </button>
                </div>

                <p className="ask-suggestion-count" aria-live="polite">
                    {suggestionIndex + 1} / {prefilled_questions.length}
                </p>

                <Composer value={draft} onChange={setDraft} onSubmit={askQuestion} isThinking={isThinking} autoFocus />

                {answerResponse && (
                    <section className="ask-answer" aria-labelledby="answer-title">
                        <header className="ask-answer-header">
                            <div className="ask-answer-title">
                                <CheckIcon aria-hidden="true" />
                                <h2 id="answer-title">Your answer</h2>
                            </div>
                            <span>AI-generated · Review the citations</span>
                        </header>
                        <p className="ask-answer-question">{answeredQuestion}</p>
                        <Answer
                            {...answerResponse}
                            activeSourceId={viewerSource?.source_id ?? null}
                            onSourceClick={handleSourceClick}
                        />
                    </section>
                )}
                <div className="sr-only" role="status">
                    {isThinking ? 'Preparing your answer.' : answerResponse ? 'Your answer is ready.' : ''}
                </div>
                {isThinking && (
                    <div className="ask-progress">
                        <Loader2Icon className="animate-spin" aria-hidden="true" />
                        <div>
                            <strong>Preparing your answer</strong>
                            <p>Searching your books and gathering relevant sources…</p>
                        </div>
                    </div>
                )}
                {askError && <p className="ask-request-error" role="alert">{askError}</p>}

            </section>

            {viewerSource && (
                <SourceViewer
                    source={viewerSource}
                    content={viewerContent}
                    isLoading={viewerLoading}
                    error={viewerError}
                    onClose={handleCloseViewer}
                    onRetry={handleRetryViewer}
                />
            )}

            <p className="ask-disclaimer">
                <ShieldAlertIcon aria-hidden="true" />
                Educational use only — verify citations in the source book. Not a substitute for clinical judgement.
            </p>
        </div>
    )
}

export default Ask
