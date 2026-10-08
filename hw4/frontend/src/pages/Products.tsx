import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { fetchProducts, shortDescription, type Product } from '../api'
import { CATEGORIES, garmentFamily } from '../categories'
import ProductCard from '../components/ProductCard'

export default function Products() {
  const [products, setProducts] = useState<Product[] | null>(null)
  const [error, setError] = useState('')
  const [params, setParams] = useSearchParams()
  const category = params.get('category') ?? ''

  useEffect(() => {
    fetchProducts().then(setProducts).catch((e: Error) => setError(e.message))
  }, [])

  if (error) return <p className="page">Could not load products: {error}</p>
  if (!products) return <p className="page">Loading products…</p>

  const shown = category ? products.filter((p) => garmentFamily(p.garment_type) === category) : products
  const label = CATEGORIES.find((c) => c.key === category)?.label ?? 'All products'

  return (
    <section className="page">
      <div className="page-head">
        <p className="eyebrow">The collection</p>
        <h1>{label}</h1>
        <p className="muted">{shown.length} {shown.length === 1 ? 'piece' : 'pieces'} · live stock by size on every card</p>
      </div>
      <div className="filter-bar" role="group" aria-label="Filter by category">
        <button type="button" className={`filter-pill ${category ? '' : 'active'}`} onClick={() => setParams({})}>
          All
        </button>
        {CATEGORIES.map((c) => (
          <button
            key={c.key}
            type="button"
            className={`filter-pill ${category === c.key ? 'active' : ''}`}
            aria-pressed={category === c.key}
            onClick={() => setParams({ category: c.key })}
          >
            {c.label}
          </button>
        ))}
      </div>
      <div className="product-grid">
        {shown.map((p) => (
          <ProductCard key={p.product_id} product={{ ...p, short_description: shortDescription(p.description) }} />
        ))}
      </div>
    </section>
  )
}
