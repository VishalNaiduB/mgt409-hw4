import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { fetchProduct, formatPrice, type Product } from '../api'
import StockBadge from '../components/StockBadge'

const SWATCHES: [string, string][] = [
  ['navy', '#14284b'], ['heather', '#b9bcc2'], ['gray', '#9ea3aa'], ['grey', '#9ea3aa'], ['charcoal', '#4a4d52'],
  ['white', '#ffffff'], ['black', '#1b1b1b'], ['red', '#b3261e'], ['maroon', '#6d1f2a'], ['royal', '#2a52be'],
  ['blue', '#286dc0'], ['green', '#2e6b3f'], ['pink', '#e8a3b8'], ['coral', '#e08a73'], ['cream', '#f1e8d2'],
  ['gold', '#c9a227'], ['yellow', '#f2c94c'], ['orange', '#e07b39'], ['purple', '#6b4c9a'], ['brown', '#7a5236'],
]

function swatch(colour: string): string {
  const c = colour.toLowerCase()
  return SWATCHES.find(([k]) => c.includes(k))?.[1] ?? '#d9d6cf'
}

export default function ProductDetail({ onAskAssistant }: { onAskAssistant: () => void }) {
  const { productId = '' } = useParams()
  const [loaded, setLoaded] = useState<{ id: string; product?: Product; error?: string } | null>(null)

  useEffect(() => {
    fetchProduct(productId)
      .then((product) => setLoaded({ id: productId, product }))
      .catch((e: Error) => setLoaded({ id: productId, error: e.message }))
  }, [productId])

  if (!loaded || loaded.id !== productId) return <p className="page">Loading…</p>
  if (loaded.error || !loaded.product) return <p className="page">Could not load this product: {loaded.error}</p>
  const { product } = loaded

  return (
    <section className="page">
      <nav className="breadcrumb" aria-label="Breadcrumb">
        <Link to="/products">Products</Link>
        <span aria-hidden="true">/</span>
        <span>{product.name}</span>
      </nav>
      <div className="product-detail">
        <div className="detail-print">
          <img src={product.image_url} alt={product.name} />
        </div>
        <div className="detail-info">
          <p className="eyebrow">{product.garment_type}</p>
          <h1>{product.name}</h1>
          <p className="price large">{formatPrice(product.price)}</p>
          <p className="detail-description">{product.description}</p>

          <h2 className="detail-label">Colors</h2>
          <ul className="swatches">
            {product.colors.map((c) => (
              <li key={c}>
                <span className="swatch" style={{ background: swatch(c) }} aria-hidden="true" />
                {c}
              </li>
            ))}
          </ul>

          <h2 className="detail-label">Sizes</h2>
          <ul className="size-list">
            {product.inventory?.map((s) => (
              <li key={s.size} className={s.quantity === 0 ? 'sold-out' : ''}>
                <strong>{s.size}</strong>
                <StockBadge quantity={s.quantity} detail />
              </li>
            ))}
          </ul>

          <button type="button" className="button button-ghost" onClick={onAskAssistant}>
            Ask about this item
          </button>
        </div>
      </div>
    </section>
  )
}
