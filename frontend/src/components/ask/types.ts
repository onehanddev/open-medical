export interface ISources {
    source_id: string
    page_num: number
    chapter: string | null
    section: string | null
    content: string
    document_key: string
}

export interface HistoryItem {
    role: "user" | "assistant"
    content: string
}

export interface ChatMessage {
    id: string
    question: string
    answer: string
    sources: ISources[]
    status: "streaming" | "done" | "error"
}
