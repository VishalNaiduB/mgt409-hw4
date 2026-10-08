import { LOW_STOCK, stockStatus, type SizeStock, type StockStatus } from '../api'

const LABELS: Record<StockStatus, string> = { in_stock: 'In stock', low_stock: 'Low stock', sold_out: 'Sold out' }

export default function StockBadge({ quantity, detail = false }: { quantity: number; detail?: boolean }) {
  const status = stockStatus(quantity)
  let label = LABELS[status]
  if (detail && status === 'low_stock') label = `Only ${quantity} left`
  else if (detail && status === 'in_stock') label = `In stock · ${quantity}`
  return <span className={`stock-badge ${status}`}>{label}</span>
}

export function SizePills({ sizes }: { sizes: SizeStock[] }) {
  return (
    <ul className="size-pills" aria-label="Stock by size">
      {sizes.map((s) => (
        <li
          key={s.size}
          className={`size-pill ${stockStatus(s.quantity)}`}
          title={`${s.size}: ${s.quantity <= 0 ? 'sold out' : s.quantity <= LOW_STOCK ? `only ${s.quantity} left` : 'in stock'}`}
        >
          {s.size}
        </li>
      ))}
    </ul>
  )
}
