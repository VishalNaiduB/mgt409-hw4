import { useEffect, useRef } from 'react'
import type { ChatCard } from '../api'
import ProductCard from './ProductCard'

export type ChatResultSet = { question: string; products: ChatCard[]; id: number }

export default function ChatResults({ results, onClose }: { results: ChatResultSet | null; onClose: () => void }) {
  const ref = useRef<HTMLElement>(null)

  useEffect(() => {
    if (results) ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [results])

  if (!results) return null
  return (
    <section ref={ref} className="chat-results" aria-label="Products from the chat">
      <div className="page">
        <div className="chat-results-header">
          <div>
            <p className="eyebrow">From the chat · {results.products.length} {results.products.length === 1 ? 'match' : 'matches'}</p>
            <h2>“{results.question}”</h2>
          </div>
          <button type="button" className="button button-small" onClick={onClose} aria-label="Hide chat results">Hide</button>
        </div>
        <div className="product-grid glide" key={results.id}>
          {results.products.map((p, i) => (
            <ProductCard key={p.product_id} product={p} index={i} />
          ))}
        </div>
      </div>
    </section>
  )
}
