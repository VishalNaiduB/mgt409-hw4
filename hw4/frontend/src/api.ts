export type StockStatus = 'in_stock' | 'low_stock' | 'sold_out'

export type SizeStock = { size: string; quantity: number; sold_out: boolean; status: StockStatus }

export const LOW_STOCK = 5

export function stockStatus(quantity: number): StockStatus {
  return quantity <= 0 ? 'sold_out' : quantity <= LOW_STOCK ? 'low_stock' : 'in_stock'
}

export type Product = {
  product_id: string
  name: string
  garment_type: string
  description: string
  colors: string[]
  search_tags: string[]
  image_file_path: string
  image_url: string
  price: number
  total_stock: number
  sizes?: SizeStock[]
  inventory?: SizeStock[]
}

export type ChatCard = {
  product_id: string
  name: string
  price: number
  image_url: string
  garment_type: string
  short_description: string
  total_stock: number
  sizes: SizeStock[]
}

export type ChatReply = { reply: string; model: string; products: ChatCard[] }

export const CHAT_ENDPOINT = '/api/chat'

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(res.status === 404 ? 'Not found' : `Request failed (${res.status})`)
  return res.json() as Promise<T>
}

export const fetchProducts = () => getJson<Product[]>('/api/products')

export const fetchProduct = (productId: string) =>
  getJson<Product>(`/api/products/${encodeURIComponent(productId)}`)

export const formatPrice = (price: number) => `$${price.toFixed(2)}`

export function shortDescription(text: string, max = 90): string {
  if (text.length <= max) return text
  const cut = text.slice(0, max)
  return `${cut.slice(0, cut.lastIndexOf(' ')).replace(/[,.;:]$/, '')}…`
}

function authHeaders(token: string | null): Record<string, string> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers.Authorization = `Bearer ${token}`
  return headers
}

async function readJson<T>(res: Response): Promise<T> {
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Something went wrong. Please try again.')
  return data as T
}

export async function sendChatMessage(message: string, token: string | null, productId: string | null): Promise<ChatReply> {
  const res = await fetch(CHAT_ENDPOINT, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ message, product_id: productId }),
  })
  return readJson<ChatReply>(res)
}

export type HistoryMessage = {
  role: 'user' | 'assistant'
  content: string
  products: ChatCard[]
  model: string | null
  created_at: string
}

export async function fetchChatHistory(token: string): Promise<HistoryMessage[]> {
  return readJson<HistoryMessage[]>(await fetch(`${CHAT_ENDPOINT}/history`, { headers: authHeaders(token) }))
}
