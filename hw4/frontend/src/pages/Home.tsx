import { Link } from 'react-router-dom'
import Patch from '../components/Patch'
import { CATEGORIES } from '../categories'

const HERO_PRINTS = [
  { id: 'basic-hoodie-big-yale', alt: 'Navy hoodie with large YALE lettering' },
  { id: 'baseball-left-chest-crewneck', alt: 'Navy Yale Baseball crewneck' },
  { id: 'champion-reverse-weave-crewneck', alt: 'Grey Champion crewneck with YALE arch lettering' },
]

export default function Home({ onAskAssistant }: { onAskAssistant: () => void }) {
  return (
    <>
      <section className="hero">
        <div className="hero-inner">
          <div className="hero-copy">
            <p className="eyebrow">57 Broadway · New Haven</p>
            <h1>Wear your Bulldog pride.</h1>
            <p className="lede">
              Officially licensed Yale gear from New Haven's own campus shop: cozy hoodies, classic crewnecks,
              everyday tees and jackets built for cold walks across Old Campus.
            </p>
            <div className="hero-actions">
              <Link to="/products" className="button button-primary">Shop the collection</Link>
              <button type="button" className="button button-ghost" onClick={onAskAssistant}>Ask our assistant</button>
            </div>
          </div>
          <div className="hero-board" aria-label="Featured pieces">
            {HERO_PRINTS.map((p, i) => (
              <Link key={p.id} to={`/products/${p.id}`} className={`hero-print hero-print-${i + 1}`}>
                <img src={`/media/products/${p.id}.jpg`} alt={p.alt} />
              </Link>
            ))}
            <div className="hero-patch">
              <Patch size="lg" />
            </div>
          </div>
        </div>
      </section>

      <section className="page">
        <div className="section-head">
          <h2>Shop by category</h2>
          <Link to="/products" className="text-link">See everything →</Link>
        </div>
        <div className="category-grid">
          {CATEGORIES.map((c) => (
            <Link key={c.key} to={`/products?category=${c.key}`} className="category-tile">
              <img src={`/media/products/${c.image}.jpg`} alt="" loading="lazy" />
              <span>{c.label}</span>
            </Link>
          ))}
        </div>
      </section>

      <section className="page feature-row">
        <div className="feature">
          <Patch size="sm" label="RC" />
          <h3>Your college, your colours</h3>
          <p>Crests for residential colleges like Benjamin Franklin, Berkeley and Saybrook.</p>
        </div>
        <div className="feature">
          <Patch size="sm" label="GD" />
          <h3>Game-day ready</h3>
          <p>Varsity sport designs and The Game graphics for cheering on the Bulldogs.</p>
        </div>
        <div className="feature">
          <Patch size="sm" label="?" />
          <h3>Ask our assistant</h3>
          <p>Not sure about a size, colour or budget? Our chat checks live stock for you.</p>
        </div>
      </section>
    </>
  )
}
