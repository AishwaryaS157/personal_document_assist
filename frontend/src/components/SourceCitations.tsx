import { useState } from 'react'
import { ChevronDown, ChevronUp, FileText } from 'lucide-react'
import type { Source } from '../types'

interface Props {
  sources: Source[]
}

export default function SourceCitations({ sources }: Props) {
  const [expanded, setExpanded] = useState(false)
  const [highlighted, setHighlighted] = useState<number | null>(null)

  if (!sources.length) return null

  const handleClick = (i: number) => {
    setHighlighted(prev => prev === i ? null : i)
  }

  return (
    <div className="mt-2 text-sm">
      <button
        onClick={() => setExpanded((e) => !e)}
        className="flex items-center gap-1 text-brand-600 hover:text-brand-800 font-medium"
      >
        {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        {sources.length} source{sources.length !== 1 ? 's' : ''}
      </button>

      {expanded && (
        <ul className="mt-2 space-y-2">
          {sources.map((src, i) => (
            <li
              key={i}
              onClick={() => handleClick(i)}
              className={`rounded-lg border p-3 cursor-pointer transition-all duration-200 ${
                highlighted === i
                  ? 'border-brand-500 bg-brand-50 shadow-md ring-2 ring-brand-300'
                  : 'border-cream-300 bg-cream-100 hover:border-brand-300 hover:bg-cream-50'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className={`flex items-center gap-1 font-medium ${highlighted === i ? 'text-brand-700' : 'text-slate-700'}`}>
                  <FileText size={13} />
                  {src.filename}
                </span>
                <span className="text-xs text-slate-400">
                  {Math.round(src.score * 100)}% match
                </span>
              </div>
              <p className={`text-xs line-clamp-3 ${highlighted === i ? 'text-brand-800' : 'text-slate-500'}`}>
                {src.content}
              </p>
              {highlighted === i && (
                <p className="text-xs text-brand-500 mt-1.5 font-medium">chunk {src.chunk_index}</p>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
