import { useEffect, useState } from "react"
import { PlusIcon } from "lucide-react"
import Upload from "@/src/components/upload/upload"
import Ask from "@/src/components/ask/ask"
import './App.css'

function getPath() {
  return window.location.pathname.replace(/\/+$/, "") || "/"
}

function navigate(to: string) {
  window.history.pushState({}, "", to)
  window.dispatchEvent(new PopStateEvent("popstate"))
}

function App() {
  const [path, setPath] = useState(() => getPath())
  const isUpload = path === "/upload"

  useEffect(() => {
    const sync = () => setPath(getPath())
    window.addEventListener("popstate", sync)
    return () => window.removeEventListener("popstate", sync)
  }, [])

  function handleNav(event: React.MouseEvent, to: string) {
    event.preventDefault()
    navigate(to)
  }
  return (
    <main className="medical-app">
      <header className="app-header">
        <a className="brand" href="/" onClick={(event) => handleNav(event, "/")} aria-label="Open Medical home">
          <span className="brand-mark"><PlusIcon aria-hidden="true" /></span>
          Open Medical<span className="brand-dot">.</span>
        </a>
        <nav className="header-nav" aria-label="Primary">
          <a
            href="/ask"
            onClick={(event) => handleNav(event, "/ask")}
            className={isUpload ? "" : "is-active"}
            aria-current={isUpload ? undefined : "page"}
          >
            Ask
          </a>
          <a
            href="/upload"
            onClick={(event) => handleNav(event, "/upload")}
            className={isUpload ? "is-active" : ""}
            aria-current={isUpload ? "page" : undefined}
          >
            Upload
          </a>
        </nav>
        <span className="header-label">{isUpload ? "YOUR DOCUMENT WORKSPACE" : "CITED MEDICAL ANSWERS"}</span>
      </header>

      {isUpload ? (
      <section className="upload-workspace" aria-labelledby="workspace-title">
        <div className="eyebrow"><span /> A little less paperwork</div>
        <h1 id="workspace-title">Get Cited answers<br /><span>From your medical textbooks</span></h1>
        <p className="workspace-description">Bring your medical document into one simple workspace.</p>

        <Upload />
        <p className="workspace-ask-link">Have a question first? <a href="/ask" onClick={(event) => handleNav(event, "/ask")}>Ask Open Medical →</a></p>
      </section>
      ) : (
        <section className="ask-workspace" aria-labelledby="ask-title">
          <Ask />
        </section>
      )}
      <footer className="app-footer"><span>OPEN MEDICAL</span><span>Made for a little more clarity.</span></footer>
    </main>
  )
}

export default App
