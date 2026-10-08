import { useEffect, useRef, useState, type FormEvent } from 'react'
import { matchPath, useLocation } from 'react-router-dom'
import { fetchChatHistory, sendChatMessage, type ChatCard } from '../api'
import { useAuth } from '../auth'
import Patch from './Patch'

type Message = { role: 'user' | 'assistant'; content: string; products?: ChatCard[]; question?: string; model?: string | null }

// The "answered by" routing tag is a development aid: shown by `npm run dev`, left out of production builds.
const SHOW_MODEL_TAG = import.meta.env.DEV

const WELCOME: Message = { role: 'assistant', content: 'Hi! Ask me about our Yale gear.' }

const GENERAL_CHIPS = ['What hoodies do you have?', 'Gifts under $40', "What's in stock in size M?", 'Anything for Saybrook?']
const PRODUCT_CHIPS = ['Is this in stock in medium?', 'What colours does this come in?', 'Show me something similar']

type Props = {
  open: boolean
  onOpenChange: (open: boolean) => void
  onResults: (question: string, products: ChatCard[]) => void
}

export default function ChatPanel({ open, onOpenChange, onResults }: Props) {
  const { token } = useAuth()
  const location = useLocation()
  const pageProductId = matchPath('/products/:productId', location.pathname)?.params.productId ?? null
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [messages, setMessages] = useState<Message[]>([WELCOME])
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let cancelled = false
    const load = token
      ? fetchChatHistory(token).then((rows) => {
          const loaded: Message[] = rows.map((r, i) => ({
            role: r.role,
            content: r.content,
            products: r.products,
            model: r.model,
            question: r.role === 'assistant' && rows[i - 1]?.role === 'user' ? rows[i - 1].content : undefined,
          }))
          return [WELCOME, ...loaded]
        })
      : Promise.resolve([WELCOME])
    load
      .catch(() => [WELCOME])
      .then((msgs) => {
        if (!cancelled) setMessages(msgs)
      })
    return () => {
      cancelled = true
    }
  }, [token])

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [messages, open, sending])

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    send(input)
  }

  async function send(raw: string) {
    const text = raw.trim()
    if (!text || sending) return
    setInput('')
    setMessages((m) => [...m, { role: 'user', content: text }])
    setSending(true)
    try {
      const { reply, products, model } = await sendChatMessage(text, token, pageProductId)
      setMessages((m) => [...m, { role: 'assistant', content: reply, products, question: text, model }])
      if (products.length) onResults(text, products)
    } catch (err) {
      setMessages((m) => [...m, { role: 'assistant', content: (err as Error).message }])
    } finally {
      setSending(false)
    }
  }

  if (!open) {
    return (
      <button className="chat-toggle" onClick={() => onOpenChange(true)} aria-label="Open chat">
        <Patch size="sm" />
        <span className="chat-toggle-label">Ask Campus Customs</span>
      </button>
    )
  }

  return (
    <div className="chat-panel" role="dialog" aria-label="Shopping assistant">
      <div className="chat-header">
        <Patch size="sm" />
        <div className="chat-title">
          <strong>Campus Customs assistant</strong>
          <span>Live prices and stock from our shelves</span>
        </div>
        <button className="chat-close" onClick={() => onOpenChange(false)} aria-label="Close chat">×</button>
      </div>
      <div className="chat-messages">
        {messages.map((m, i) => (
          <div key={i} className={`chat-message ${m.role}`}>
            {m.content}
            {m.products?.length ? (
              <button
                type="button"
                className="chat-note link-button"
                onClick={() => onResults(m.question ?? 'From your chat', m.products!)}
              >
                Show {m.products.length} product{m.products.length > 1 ? 's' : ''} on the page
              </button>
            ) : null}
            {SHOW_MODEL_TAG && m.model ? <span className="answered-by">answered by {m.model}</span> : null}
          </div>
        ))}
        {sending && <div className="chat-message assistant typing">Thinking…</div>}
        <div ref={endRef} />
      </div>
      <div className="chat-chips" aria-label="Suggested questions">
        {(pageProductId ? PRODUCT_CHIPS : GENERAL_CHIPS).map((chip) => (
          <button key={chip} type="button" className="chip" disabled={sending} onClick={() => send(chip)}>
            {chip}
          </button>
        ))}
      </div>
      <form className="chat-input" onSubmit={onSubmit}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={pageProductId ? 'Ask about this product…' : 'Ask about a product…'}
          aria-label="Chat message"
        />
        <button type="submit" disabled={sending}>Send</button>
      </form>
    </div>
  )
}
