import type { ReactNode } from "react"

export default function ThinkingIndicator({ children }: { children?: ReactNode }) {
    return (
        <div className="ask-thinking" role="status" aria-label="Searching your books">
            {children}
            <span className="typing-dots" aria-hidden="true">
                <span />
                <span />
                <span />
            </span>
        </div>
    )
}
