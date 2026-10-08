import type { CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { formatPrice, type SizeStock } from '../api'
import StockBadge, { SizePills } from './StockBadge'

export type CardData = {
  product_id: string
  name: string
  price: number
  image_url: string
  short_description: string
  total_stock: number
  sizes?: SizeStock[]
}

export default function ProductCard({ product, index = 0 }: { product: CardData; index?: number }) {
  return (
    <Link to={`/products/${product.product_id}`} className="product-card" style={{ '--i': index } as CSSProperties}>
      <div className="card-print">
        <img src={product.image_url} alt={product.name} loading="lazy" />
        <StockBadge quantity={product.total_stock} />
      </div>
      <div className="product-card-body">
        <h3>{product.name}</h3>
        <p className="muted">{product.short_description}</p>
        <div className="card-foot">
          <p className="price">{formatPrice(product.price)}</p>
          {product.sizes?.length ? <SizePills sizes={product.sizes} /> : null}
        </div>
      </div>
    </Link>
  )
}
