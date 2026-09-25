import { API_URL } from "@/src/getEnv"
import type { HistoryItem, ISources } from "./types"

interface StreamCallbacks {
    onToken: (token: string) => void
    onSources: (sources: ISources[]) => void
}

// Minimal SSE reader: parses `data: {...}` frames until [DONE].
export async function streamAsk(
    query: string,
    history: HistoryItem[],
    callbacks: StreamCallbacks,
    signal: AbortSignal,
): Promise<void> {
    const response = await fetch(`${API_URL}/ask/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, history }),
        signal,
    })
    if (!response.ok) throw new Error("request-failed")
    if (!response.body) throw new Error("no-stream")

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ""

    while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const events = buffer.split("\n\n")
        buffer = events.pop() ?? ""
        for (const event of events) {
            const line = event.split("\n").find((l) => l.startsWith("data: "))
            if (!line) continue
            const data = line.slice(6)
            if (data === "[DONE]") continue
            const message = JSON.parse(data)
            if (message.type === "token") callbacks.onToken(message.content)
            if (message.type === "sources") callbacks.onSources(message.sources)
        }
    }
}
