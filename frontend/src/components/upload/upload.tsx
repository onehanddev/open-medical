import { useState } from "react"
import {
    Attachment,
    AttachmentAction,
    AttachmentActions,
    AttachmentContent,
    AttachmentDescription,
    AttachmentMedia,
    AttachmentTitle,
} from "../../../components/ui/attachment"
import { Button } from "../../../components/ui/button"
import { useRef, type ChangeEvent, type DragEvent } from "react"
import { ArrowUpIcon, CheckIcon, FileTextIcon, UploadIcon, XIcon } from "lucide-react"
import { normalizeUploadFileName, useUploadPdf } from "@/src/components/upload/useUploadPdf"

import '@/src/App.css'

const Upload = () => {
    const [pdf, setPdf] = useState<File | null>(null)
    const [fileName, setFileName] = useState("")
    const [submittedName, setSubmittedName] = useState<string | null>(null)
    const [error, setError] = useState("")
    const [isDragging, setIsDragging] = useState(false)
    const inputRef = useRef<HTMLInputElement>(null)
    const dragDepth = useRef(0)
    const { mutate, isPending, isSuccess, error: uploadError, reset } = useUploadPdf();



    function selectFiles(files: FileList | null) {
        if (isPending || !files?.length) return
        if (files.length !== 1) {
            setError("Please choose one PDF at a time.")
            return
        }
        const file = files[0]
        if (file.type !== "application/pdf" && !(file.type === "" && /\.pdf$/i.test(file.name))) {
            setError("That file isn’t a PDF. Please choose a .pdf file.")
            return
        }
        setError("")
        reset()
        setPdf(file)
        setFileName(file.name)
        setSubmittedName(null)
    }

    function confirmUpload(name: string) {
        if (!pdf || isPending) return
        if (!name.trim()) {
            setError("Please enter a name for your file.")
            return
        }
        setError("")
        const resolved = normalizeUploadFileName(name, pdf.name)
        setSubmittedName(resolved)
        mutate({ file: pdf, fileName: name })
    }

    function retryUpload() {
        if (!pdf || !submittedName || isPending) return
        setError("")
        mutate({ file: pdf, fileName: submittedName })
    }

    function clearSelection() {
        setPdf(null)
        setFileName("")
        setSubmittedName(null)
        setError("")
        reset()
    }

    function handlePdfChange(event: ChangeEvent<HTMLInputElement>) {
        selectFiles(event.target.files)
        event.target.value = ""
    }

    function handleDrop(event: DragEvent<HTMLElement>) {
        event.preventDefault()
        dragDepth.current = 0
        setIsDragging(false)
        selectFiles(event.dataTransfer.files)
    }

    function formatSize(bytes: number) {
        return bytes < 1024 * 1024 ? `${Math.ceil(bytes / 1024)} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    }

    const previewName = pdf ? normalizeUploadFileName(fileName, pdf.name) : ""


    return <><input ref={inputRef} type="file" accept=".pdf,application/pdf" onChange={handlePdfChange} hidden aria-label="Choose a PDF" />

        {!pdf ? (
            <section
                className={`pdf-dropzone${isDragging ? " is-dragging" : ""}`}
                aria-label="PDF drop area"
                onDragEnter={(event) => {
                    event.preventDefault()
                    dragDepth.current += 1
                    setIsDragging(true)
                }}
                onDragOver={(event) => {
                    event.preventDefault()
                    event.dataTransfer.dropEffect = "copy"
                }}
                onDragLeave={(event) => {
                    event.preventDefault()
                    dragDepth.current = Math.max(0, dragDepth.current - 1)
                    if (dragDepth.current === 0) setIsDragging(false)
                }}
                onDrop={handleDrop}
            >
                <div className="document-art" aria-hidden="true">
                    <div className="document-back" />
                    <div className="document-front"><FileTextIcon /><span>PDF</span></div>
                    <span className="upload-bubble"><ArrowUpIcon /></span>
                </div>
                <h2>{isDragging ? "Drop it right here" : "Drop your PDF here"}</h2>
                <p className="drop-description">or choose a file from your device</p>
                <Button className="upload-button" onClick={() => inputRef.current?.click()} aria-describedby={error ? "pdf-error" : "pdf-hint"}>
                    <UploadIcon aria-hidden="true" /> Upload PDF
                </Button>
                <p id="pdf-hint" className="file-hint">PDF format <span>·</span> One document at a time</p>
            </section>
        ) : submittedName === null ? (
            <section className="selected-panel" aria-label="Name your document">
                <div className="selected-heading"><span className="selected-check"><CheckIcon aria-hidden="true" /></span><h2>Give your PDF a name</h2></div>
                <p className="drop-description">This is the name saved with your file. Keep the original or type a new one.</p>
                <Attachment className="selected-attachment">
                    <AttachmentMedia><FileTextIcon aria-hidden="true" /></AttachmentMedia>
                    <AttachmentContent>
                        <AttachmentTitle title={pdf.name}>{pdf.name}</AttachmentTitle>
                        <AttachmentDescription>
                            PDF · {formatSize(pdf.size)}
                        </AttachmentDescription>
                    </AttachmentContent>
                    <AttachmentActions>
                        <AttachmentAction type="button" aria-label={`Remove ${pdf.name}`} onClick={clearSelection}><XIcon /></AttachmentAction>
                    </AttachmentActions>
                </Attachment>
                <div className="name-field">
                    <label htmlFor="pdf-name">File name</label>
                    <input
                        id="pdf-name"
                        type="text"
                        className="name-input"
                        value={fileName}
                        maxLength={255}
                        autoComplete="off"
                        spellCheck={false}
                        onChange={(event) => setFileName(event.target.value)}
                        aria-describedby="pdf-name-preview"
                    />
                    <p id="pdf-name-preview" className="name-preview">Will be saved as <strong>{previewName}</strong></p>
                </div>
                <div className="name-actions">
                    <Button className="upload-button name-upload-button" onClick={() => confirmUpload(fileName)}>
                        <UploadIcon aria-hidden="true" /> Upload with this name
                    </Button>
                    <Button variant="ghost" className="keep-button" onClick={() => confirmUpload(pdf.name)}>Keep original name</Button>
                </div>
                <Button variant="ghost" className="replace-button" onClick={() => inputRef.current?.click()}><UploadIcon aria-hidden="true" /> Choose another PDF</Button>
            </section>
        ) : (
            <section className="selected-panel" aria-label="Selected document">
                <div className="selected-heading"><span className="selected-check"><CheckIcon aria-hidden="true" /></span><h2>{isPending ? "Uploading your PDF…" : isSuccess ? "Your PDF is uploaded" : "Upload failed"}</h2></div>
                <p className="drop-description">{isPending ? "Please wait while your document uploads." : isSuccess ? `Saved as ${submittedName}.` : "Please try again or rename your file."}</p>
                <Attachment className="selected-attachment">
                    <AttachmentMedia><FileTextIcon aria-hidden="true" /></AttachmentMedia>
                    <AttachmentContent>
                        <AttachmentTitle title={submittedName}>{submittedName}</AttachmentTitle>
                        <AttachmentDescription>
                            PDF · {formatSize(pdf.size)}
                        </AttachmentDescription>
                    </AttachmentContent>
                    <AttachmentActions>
                        <AttachmentAction type="button" aria-label={`Remove ${submittedName}`} disabled={isPending} onClick={clearSelection}><XIcon /></AttachmentAction>
                    </AttachmentActions>
                </Attachment>
                {!isPending && !isSuccess && (
                    <div className="name-actions">
                        <Button className="upload-button name-upload-button" onClick={retryUpload}>
                            <UploadIcon aria-hidden="true" /> Try again
                        </Button>
                        <Button variant="ghost" className="keep-button" onClick={() => { setFileName(submittedName); setSubmittedName(null); setError(""); reset() }}>Rename</Button>
                    </div>
                )}
                <Button variant="ghost" className="replace-button" disabled={isPending} onClick={() => inputRef.current?.click()}><UploadIcon aria-hidden="true" /> Choose another PDF</Button>
            </section>
        )}
        <div aria-live="polite">{(error || uploadError) && <p id="pdf-error" role="alert" className="upload-error">{error || uploadError?.message}</p>}</div>
        <p className="workspace-note">A clearer picture starts with a single document.</p>
    </>
}

export default Upload;
