import { useState } from 'react'
import { Link, NavLink, Route, Routes } from 'react-router-dom'
import type { ChatCard } from './api'
import { useAuth } from './auth'
import ChatPanel from './components/ChatPanel'
import ChatResults, { type ChatResultSet } from './components/ChatResults'
import Patch from './components/Patch'
import About from './pages/About'
import CreateAccount from './pages/CreateAccount'
import Home from './pages/Home'
import Login from './pages/Login'
import ProductDetail from './pages/ProductDetail'
import Products from './pages/Products'

export default function App() {
  const { user, logout } = useAuth()
  const [chatResults, setChatResults] = useState<ChatResultSet | null>(null)
  const [chatOpen, setChatOpen] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)

  function showResults(question: string, products: ChatCard[]) {
    setChatResults({ question, products, id: Date.now() })
  }

  return (
    <>
      <header className="navbar">
        <div className="navbar-inner">
          <Link to="/" className="brand" aria-label="Campus Customs home" onClick={() => setMenuOpen(false)}>
            <Patch size="sm" />
            <span className="brand-name">Campus Customs</span>
          </Link>
          <button
            type="button"
            className="menu-toggle"
            aria-expanded={menuOpen}
            aria-controls="site-nav"
            onClick={() => setMenuOpen((o) => !o)}
          >
            {menuOpen ? 'Close' : 'Menu'}
          </button>
          <nav id="site-nav" className={menuOpen ? 'open' : ''} onClick={() => setMenuOpen(false)}>
            <NavLink to="/" end>Home</NavLink>
            <NavLink to="/products">Products</NavLink>
            <NavLink to="/about">About Us</NavLink>
            {user ? (
              <>
                <span className="nav-user">Hi, {user.first_name || user.name}</span>
                <button type="button" className="nav-button" onClick={logout}>Log out</button>
              </>
            ) : (
              <>
                <NavLink to="/login">Log in</NavLink>
                <NavLink to="/create-account" className="nav-cta">Create account</NavLink>
              </>
            )}
          </nav>
        </div>
      </header>
      <main>
        <ChatResults results={chatResults} onClose={() => setChatResults(null)} />
        <Routes>
          <Route path="/" element={<Home onAskAssistant={() => setChatOpen(true)} />} />
          <Route path="/products" element={<Products />} />
          <Route path="/products/:productId" element={<ProductDetail onAskAssistant={() => setChatOpen(true)} />} />
          <Route path="/about" element={<About />} />
          <Route path="/login" element={<Login />} />
          <Route path="/create-account" element={<CreateAccount />} />
          <Route
            path="*"
            element={<section className="page"><h1>Page not found</h1><p><Link to="/">Back to the shop</Link></p></section>}
          />
        </Routes>
      </main>
      <footer className="site-footer">
        <div className="footer-inner">
          <div className="footer-brand">
            <Patch size="sm" />
            <div>
              <strong>Campus Customs</strong>
              <p>57 Broadway, New Haven, CT</p>
            </div>
          </div>
          <p className="footer-note">Officially licensed Yale apparel for students, alumni, families and fans.</p>
          <nav className="footer-links" aria-label="Footer">
            <Link to="/products">Shop all</Link>
            <Link to="/about">About Us</Link>
          </nav>
        </div>
      </footer>
      <ChatPanel open={chatOpen} onOpenChange={setChatOpen} onResults={showResults} />
    </>
  )
}
