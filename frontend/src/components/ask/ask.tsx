import { useEffect, useRef, useState } from "react"
import {
    BookOpenIcon,
    CheckIcon,
    ChevronLeftIcon,
    ChevronRightIcon,
    FileTextIcon,
    GraduationCapIcon,
    Loader2Icon,
    RotateCcwIcon,
    ShieldAlertIcon,
    StethoscopeIcon,
} from "lucide-react"
import "./ask.css"
import { prefilled_questions } from "../../../static/questions"
import Answer from "./Answer"
import Composer from "./Composer"
import SourceViewer from "./SourceViewer"
import { streamAsk } from "./chatApi"
import type { ChatMessage, HistoryItem, ISources } from "./types"

const suggestionIcons = [StethoscopeIcon, GraduationCapIcon, FileTextIcon, BookOpenIcon]

function buildHistory(messages: ChatMessage[]): HistoryItem[] {
    return messages
        .filter((m) => m.status === "done")
        .flatMap((m): HistoryItem[] => [
            { role: "user", content: m.question },
            { role: "assistant", content: m.answer },
        ])
}

const Ask = () => {
    const [messages, setMessages] = useState<ChatMessage[]>([])
    const [draft, setDraft] = useState("")
    const [isThinking, setIsThinking] = useState(false)
    const [suggestionIndex, setSuggestionIndex] = useState(0)
    const [viewer, setViewer] = useState<{ messageId: string; source: ISources } | null>(null)
    const abortRef = useRef<AbortController | null>(null)
    const threadEndRef = useRef<HTMLDivElement>(null)
    const isChatting = messages.length > 0

    const suggestionQuestion = prefilled_questions[suggestionIndex]
    const SuggestionIcon = suggestionIcons[suggestionIndex]

    function shiftSuggestion(direction: number) {
        setSuggestionIndex(
            (current) => (current + direction + prefilled_questions.length) % prefilled_questions.length,
        )
    }

    // Keep the latest message in view while streaming.
    useEffect(() => {
        threadEndRef.current?.scrollIntoView({ behavior: "auto", block: "end" })
    }, [messages])

    // Abort any in-flight stream on unmount.
    useEffect(() => () => abortRef.current?.abort(), [])

    function patchMessage(id: string, patch: Partial<ChatMessage>) {
        setMessages((current) => current.map((m) => (m.id === id ? { ...m, ...patch } : m)))
    }

    async function runQuestion(id: string, question: string, history: HistoryItem[]) {
        abortRef.current?.abort()
        const controller = new AbortController()
        abortRef.current = controller
        setIsThinking(true)
        setViewer(null)
        try {
            await streamAsk(
                question,
                history,
                {
                    onToken: (token) =>
                        setMessages((current) => current.map((m) => (m.id === id ? { ...m, answer: m.answer + token } : m))),
                    onSources: (sources) => patchMessage(id, { sources }),
                },
                controller.signal,
            )
            patchMessage(id, { status: "done" })
        } catch {
            if (controller.signal.aborted) {
                setMessages((current) => current.filter((m) => m.id !== id))
            } else {
                patchMessage(id, { status: "error" })
            }
        } finally {
            if (abortRef.current === controller) {
                abortRef.current = null
                setIsThinking(false)
            }
        }
    }

    async function askQuestion(question: string) {
        const trimmed = question.trim()
        if (!trimmed || isThinking) return
        const id = `${Date.now()}-${Math.random().toString(36).slice(2)}`
        const history = buildHistory(messages)
        setMessages((current) => [...current, { id, question: trimmed, answer: "", sources: [], status: "streaming" }])
        setDraft("")
        await runQuestion(id, trimmed, history)
    }

    function retryMessage(id: string) {
        const index = messages.findIndex((m) => m.id === id)
        if (index < 0 || isThinking) return
        const history = buildHistory(messages.slice(0, index))
        patchMessage(id, { answer: "", sources: [], status: "streaming" })
        void runQuestion(id, messages[index].question, history)
    }

    function restartChat() {
        abortRef.current?.abort()
        abortRef.current = null
        setMessages([])
        setDraft("")
        setViewer(null)
        setIsThinking(false)
    }

    return (
        <div className="ask-page">
            <section className="ask-hero" aria-labelledby="ask-title">
                {!isChatting && (
                    <>
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
                    </>
                )}

                {isChatting && (
                    <div className="ask-thread-bar">
                        <span className="ask-thread-count" aria-live="polite">
                            {messages.length} question{messages.length > 1 ? "s" : ""} in this chat
                        </span>
                        <button type="button" className="ask-restart" onClick={restartChat} disabled={isThinking}>
                            <RotateCcwIcon aria-hidden="true" />
                            Restart chat
                        </button>
                    </div>
                )}

                <div className={isChatting ? "ask-thread" : undefined} role={isChatting ? "log" : undefined} aria-label={isChatting ? "Chat thread" : undefined}>
                    {messages.map((message) => (
                        <article key={message.id} className="ask-turn">
                            <p className="ask-question-bubble">{message.question}</p>
                            <section className="ask-answer" aria-label="Answer">
                                <header className="ask-answer-header">
                                    <div className="ask-answer-title">
                                        {message.status === "done" ? (
                                            <CheckIcon aria-hidden="true" />
                                        ) : (
                                            <Loader2Icon aria-hidden="true" className="animate-spin" />
                                        )}
                                        <h2>{message.status === "done" ? "Your answer" : "Searching…"}</h2>
                                    </div>
                                    <span>AI-generated · Review the citations</span>
                                </header>
                                {message.answer && (
                                    <Answer
                                        answer={message.answer}
                                        sources={message.sources}
                                        activeSourceId={viewer?.messageId === message.id ? viewer.source.source_id : null}
                                        onSourceClick={(source) => setViewer({ messageId: message.id, source })}
                                    />
                                )}
                                {message.status === "error" && (
                                    <p className="ask-request-error" role="alert">
                                        Couldn’t get an answer.{" "}
                                        <button type="button" className="ask-retry" onClick={() => retryMessage(message.id)}>
                                            Try again
                                        </button>
                                    </p>
                                )}
                            </section>
                        </article>
                    ))}
                    <div ref={threadEndRef} />
                </div>
                <div className="sr-only" role="status">
                    {isThinking ? "Preparing your answer." : messages.length > 0 ? "Your answer is ready." : ""}
                </div>

                <div className={isChatting ? "ask-composer-sticky" : undefined}>
                    <Composer value={draft} onChange={setDraft} onSubmit={askQuestion} isThinking={isThinking} autoFocus={!isChatting} />
                </div>
            </section>

            {viewer && (
                <SourceViewer
                    source={viewer.source}
                    onClose={() => setViewer(null)}
                    onPageChange={(pageNumber) =>
                        setViewer((current) =>
                            current ? { ...current, source: { ...current.source, page_num: pageNumber } } : current,
                        )
                    }
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
