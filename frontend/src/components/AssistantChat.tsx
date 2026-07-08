import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { api } from '../api/client'
import { ChatCitation, ChatMessage } from '../types'
import './AssistantChat.css'

interface Props {
  scopeClientId?: string
  scopeName?: string
  compact?: boolean
}

const DOC_LABELS: Record<string, string> = {
  call_note: 'Call note',
  contact_note: 'Contact note',
  life_event: 'Life event',
  exposure: 'Exposure',
  rationale: 'Rationale',
  trace: 'Agent finding',
  market: 'Market signal',
}

function CitationChip({ c }: { c: ChatCitation }) {
  const label = `${c.client_id || 'Market'}${c.date ? ` · ${c.date}` : ''}`
  const title = `${DOC_LABELS[c.doc_type] ?? c.doc_type}: ${c.snippet}`
  if (c.client_id) {
    return (
      <Link to={`/clients/${c.client_id}`} className="chip chat__cite" title={title}>
        <span className="mono">{label}</span>
        <span className="chat__cite-name">{c.name}</span>
      </Link>
    )
  }
  return (
    <span className="chip chat__cite chat__cite--static" title={title}>
      <span className="mono">{label}</span>
      <span className="chat__cite-name">{c.name}</span>
    </span>
  )
}

export default function AssistantChat({ scopeClientId, scopeName, compact }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let live = true
    api.chatSuggestions(scopeClientId)
      .then((s) => { if (live) setSuggestions(s) })
      .catch(() => { if (live) setSuggestions([]) })
    return () => { live = false }
  }, [scopeClientId])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  async function send(query: string) {
    const q = query.trim()
    if (!q || busy) return
    setInput('')
    setBusy(true)
    setMessages((m) => [
      ...m,
      { role: 'user', content: q },
      { role: 'assistant', content: '', pending: true },
    ])
    try {
      const res = await api.chat(q, scopeClientId)
      setMessages((m) => {
        const next = [...m]
        next[next.length - 1] = {
          role: 'assistant',
          content: res.answer,
          citations: res.citations,
          grounded: res.grounded,
        }
        return next
      })
    } catch {
      setMessages((m) => {
        const next = [...m]
        next[next.length - 1] = {
          role: 'assistant',
          content: 'Something went wrong reaching the copilot. Is the API running?',
          grounded: false,
        }
        return next
      })
    } finally {
      setBusy(false)
    }
  }

  const empty = messages.length === 0

  return (
    <div className={`chat${compact ? ' chat--compact' : ''}`}>
      <div className="chat__log" ref={scrollRef}>
        {empty && (
          <div className="chat__intro">
            <p className="chat__intro-text">
              {scopeName
                ? `Ask about ${scopeName} — grounded in their notes, life events, and the agent's reasoning.`
                : 'Ask about your book. Every answer is grounded in your records and cites its sources.'}
            </p>
          </div>
        )}

        {messages.map((m, i) => (
          <motion.div
            key={i}
            className={`chat__msg chat__msg--${m.role}`}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
          >
            {m.pending ? (
              <div className="chat__typing"><span /><span /><span /></div>
            ) : (
              <>
                <div className="chat__bubble">{m.content}</div>
                {m.role === 'assistant' && m.citations && m.citations.length > 0 && (
                  <div className="chat__cites">
                    <span className="eyebrow chat__cites-label">Sources</span>
                    <div className="chip-row">
                      {m.citations.map((c, j) => <CitationChip key={j} c={c} />)}
                    </div>
                  </div>
                )}
                {m.role === 'assistant' && m.grounded === false && !m.pending && (
                  <span className="chat__nogrounding">No matching records found</span>
                )}
              </>
            )}
          </motion.div>
        ))}
      </div>

      {empty && suggestions.length > 0 && (
        <div className="chat__suggestions">
          {suggestions.map((s) => (
            <button key={s} className="chip chat__suggestion" onClick={() => send(s)} disabled={busy}>
              {s}
            </button>
          ))}
        </div>
      )}

      <form
        className="chat__form"
        onSubmit={(e) => { e.preventDefault(); send(input) }}
      >
        <input
          className="chat__input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={scopeName ? `Ask about ${scopeName}…` : 'Ask about your book…'}
          disabled={busy}
        />
        <button className="chat__send" type="submit" disabled={busy || !input.trim()}>
          Ask
        </button>
      </form>
    </div>
  )
}
