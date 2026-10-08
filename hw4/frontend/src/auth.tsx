import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

export type User = { id: number; name: string; first_name: string | null; last_name: string | null; email: string }

export type SignupData = {
  first_name: string
  last_name: string
  email: string
  password: string
  confirm_password: string
}

type AuthState = {
  user: User | null
  token: string | null
  ready: boolean
  login: (email: string, password: string) => Promise<void>
  signup: (data: SignupData) => Promise<void>
  logout: () => void
}

const TOKEN_KEY = 'cc_token'
const AuthContext = createContext<AuthState | null>(null)

function readToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

function storeToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    // storage unavailable: the session just won't survive a reload
  }
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Something went wrong. Please try again.')
  return data as T
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(readToken)
  const [user, setUser] = useState<User | null>(null)
  const [ready, setReady] = useState(() => !readToken())

  useEffect(() => {
    if (!token || user) return
    fetch('/api/auth/me', { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => (res.ok ? res.json() : Promise.reject()))
      .then((u: User) => setUser(u))
      .catch(() => {
        storeToken(null)
        setToken(null)
      })
      .finally(() => setReady(true))
  }, [token, user])

  function start(session: { token: string; user: User }) {
    storeToken(session.token)
    setToken(session.token)
    setUser(session.user)
    setReady(true)
  }

  const value: AuthState = {
    user,
    token,
    ready,
    login: async (email, password) => start(await postJson('/api/auth/login', { email, password })),
    signup: async (data) => start(await postJson('/api/auth/signup', data)),
    logout: () => {
      storeToken(null)
      setToken(null)
      setUser(null)
    },
  }
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react/only-export-components
export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
