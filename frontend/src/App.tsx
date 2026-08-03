import { useEffect, useState } from 'react'
import { PanelLeftClose, PanelLeftOpen, LogOut } from 'lucide-react'
import { fetchDocuments } from './api/client'
import type { Document } from './types'
import DocumentPanel from './components/DocumentPanel'
import ChatInterface from './components/ChatInterface'
import AuthPage from './components/AuthPage'
import { useAuth } from './contexts/AuthContext'

export default function App() {
  const { session, email, loading, logout } = useAuth()
  const [documents, setDocuments] = useState<Document[]>([])
  const [sidebarOpen, setSidebarOpen] = useState(true)

  useEffect(() => {
    if (!session) return
    fetchDocuments().then(setDocuments).catch(console.error)
  }, [session])

  if (loading) return (
    <div className="h-screen flex items-center justify-center bg-cream-100">
      <div className="w-6 h-6 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
    </div>
  )

  if (!session) return <AuthPage />

  const handleUploaded = (doc: Document) => setDocuments(prev => [...prev, doc])
  const handleDeleted = (id: string) => setDocuments(prev => prev.filter(d => d.id !== id))

  return (
    <div className="flex h-screen bg-cream-100 text-slate-900 overflow-hidden">
      {sidebarOpen && (
        <aside className="w-72 flex-shrink-0 bg-cream-200 border-r border-cream-300 flex flex-col">
          <div className="flex items-center justify-between px-4 py-3 border-b border-cream-300">
            <div className="flex items-center gap-2">
              <img src="/logo.png" alt="logo" className="h-8 w-8 object-contain" />
              <span className="font-semibold text-brand-600 text-sm">Doc Assistant</span>
            </div>
            <button onClick={() => setSidebarOpen(false)} className="text-slate-400 hover:text-slate-600">
              <PanelLeftClose size={18} />
            </button>
          </div>
          <div className="flex-1 overflow-hidden">
            <DocumentPanel documents={documents} onUploaded={handleUploaded} onDeleted={handleDeleted} />
          </div>
        </aside>
      )}

      <main className="flex-1 flex flex-col overflow-hidden">
        <header className="flex items-center gap-3 px-4 py-3 border-b border-cream-300 bg-cream-50">
          {!sidebarOpen && (
            <button onClick={() => setSidebarOpen(true)} className="text-slate-400 hover:text-slate-600">
              <PanelLeftOpen size={18} />
            </button>
          )}
          <h1 className="text-sm font-semibold text-slate-700">Personal Document Assistant</h1>
          <div className="ml-auto flex items-center gap-3">
            <span className="text-xs text-slate-400 hidden sm:block">{email}</span>
            <span className="text-xs text-slate-400">
              {documents.length} doc{documents.length !== 1 ? 's' : ''}
            </span>
            <button
              onClick={() => logout()}
              title="Sign out"
              className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-red-500 transition-colors"
            >
              <LogOut size={14} />
              <span className="hidden sm:inline">Sign out</span>
            </button>
          </div>
        </header>

        <div className="flex-1 overflow-hidden">
          <ChatInterface />
        </div>
      </main>
    </div>
  )
}
