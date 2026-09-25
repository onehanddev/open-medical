import { useEffect, useRef, type FormEvent } from "react"
import { ArrowUpIcon, Loader2Icon, SparklesIcon } from "lucide-react"
import { Button } from "../../../components/ui/button"
import { cn } from "cn"

const MAX_QUESTION_LENGTH = 1000

export default function Composer({
    value,
    onChange,
    onSubmit,
    isThinking,
    autoFocus = false,
}: {
    value: string
    onChange: (next: string) => void
    onSubmit: (question: string) => Promise<void> | void
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
