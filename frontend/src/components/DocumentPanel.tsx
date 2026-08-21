import { useRef, useState } from 'react'
import { Upload, Trash2, FileText, Loader2 } from 'lucide-react'
import { uploadDocument, deleteDocument, fetchDocuments } from '../api/client'
import type { Document } from '../types'

// A large upload can outlive the proxy's patience: the request errors in the
// browser while the server keeps working and finishes the ingest. Rather than
// report a failure the user can disprove by reloading, poll the document list
// for a while and see whether the file actually arrived.
const RECOVER_ATTEMPTS = 8
const RECOVER_DELAY_MS = 3000

interface Props {
  documents: Document[]
  onUploaded: (doc: Document) => void
  onDeleted: (id: string) => void
}

export default function DocumentPanel({ documents, onUploaded, onDeleted }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [recovering, setRecovering] = useState<string | null>(null)

  /** Poll for a document that isn't among `known`, appearing under `filename`. */
  const waitForUpload = async (
    filename: string,
    known: Set<string>,
  ): Promise<Document | null> => {
    for (let attempt = 0; attempt < RECOVER_ATTEMPTS; attempt++) {
      await new Promise((r) => setTimeout(r, RECOVER_DELAY_MS))
      try {
        const docs = await fetchDocuments()
        const match = docs.find((d) => d.filename === filename && !known.has(d.id))
        if (match) return match
      } catch {
        // The list call can fail transiently too; keep waiting.
      }
    }
    return null
  }

  const handleFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return
    setError(null)
    setUploading(true)
    // Tracked here rather than read from props, so files uploaded earlier in
    // this same batch aren't mistaken for the one we're waiting on.
    const known = new Set(documents.map((d) => d.id))
    try {
      for (const file of Array.from(files)) {
        try {
          const doc = await uploadDocument(file)
          known.add(doc.id)
          onUploaded(doc)
        } catch (e) {
          setRecovering(file.name)
          const recovered = await waitForUpload(file.name, known)
          setRecovering(null)
          if (recovered) {
            known.add(recovered.id)
            onUploaded(recovered)
          } else {
            setError(e instanceof Error ? e.message : 'Upload failed')
          }
        }
      }
    } finally {
      setUploading(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  const handleDelete = async (id: string) => {
    setDeletingId(id)
    try {
      await deleteDocument(id)
      onDeleted(id)
    } catch {
      setError('Failed to delete document')
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="flex flex-col h-full p-4 gap-4">
      <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wide">Documents</h2>

      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          handleFiles(e.dataTransfer.files)
        }}
        className={`flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-6 cursor-pointer transition-colors ${
          dragging
            ? 'border-brand-400 bg-brand-50'
            : 'border-cream-300 hover:border-brand-300 hover:bg-cream-50'
        }`}
      >
        {uploading ? (
          <Loader2 size={22} className="animate-spin text-brand-500" />
        ) : (
          <Upload size={22} className="text-slate-400" />
        )}
        <p className="text-xs text-slate-500 text-center">
          {recovering
            ? `Still processing ${recovering}… large files can take a minute`
            : uploading
              ? 'Uploading…'
              : 'Click or drag PDF, TXT, MD files here'}
        </p>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.txt,.md,.markdown"
          multiple
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>

      {error && (
        <p className="text-xs text-red-500 bg-red-50 rounded-lg px-3 py-2">{error}</p>
      )}

      <div className="flex-1 overflow-y-auto scrollbar-thin space-y-2">
        {documents.length === 0 ? (
          <p className="text-xs text-slate-400 text-center mt-4">No documents yet</p>
        ) : (
          documents.map((doc) => (
            <div
              key={doc.id}
              className="flex items-start justify-between gap-2 rounded-lg border border-cream-300 bg-cream-50 px-3 py-2.5 hover:bg-cream-100 transition-colors"
            >
              <div className="flex items-start gap-2 min-w-0">
                <FileText size={16} className="text-brand-400 mt-0.5 flex-shrink-0" />
                <div className="min-w-0">
                  <p className="text-sm font-medium text-slate-700 truncate">{doc.filename}</p>
                  <p className="text-xs text-slate-400">
                    {doc.chunk_count} chunk{doc.chunk_count !== 1 ? 's' : ''}
                  </p>
                </div>
              </div>
              <button
                onClick={() => handleDelete(doc.id)}
                disabled={deletingId === doc.id}
                className="text-slate-400 hover:text-red-500 disabled:opacity-40 transition-colors flex-shrink-0"
              >
                {deletingId === doc.id ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <Trash2 size={14} />
                )}
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
