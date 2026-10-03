import type { Book, BookPage, DailyReport, PageSales, Sale, StockMovement, StoreConfig, User } from './types'

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...options,
    credentials: 'include',
    headers: {
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...options.headers,
    },
  })
  if (!response.ok) {
    const problem = await response.json().catch(() => null) as { detail?: string | Array<{ msg: string }> } | null
    const detail = Array.isArray(problem?.detail)
      ? problem.detail.map((issue) => issue.msg).join(', ')
      : problem?.detail
    throw new Error(detail || `Error ${response.status}`)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const api = {
  login: (username: string, password: string) => request<User>('/auth/login', {
    method: 'POST', body: JSON.stringify({ username, password }),
  }),
  logout: () => request<void>('/auth/logout', { method: 'POST' }),
  me: () => request<User>('/auth/me'),
  publicConfig: () => request<StoreConfig>('/config/public'),
  users: () => request<User[]>('/users'),
  createUser: (username: string, password: string, role: User['role']) => request<User>('/users', {
    method: 'POST', body: JSON.stringify({ username, password, role }),
  }),
  updateUser: (id: string, changes: { role?: User['role']; is_active?: boolean; password?: string }) => request<User>(`/users/${id}`, {
    method: 'PATCH', body: JSON.stringify(changes),
  }),
  books: (params: URLSearchParams) => request<BookPage>(`/books?${params}`),
  createBook: (book: Omit<Book, 'id' | 'is_active' | 'created_at' | 'updated_at'>) => request<Book>('/books', {
    method: 'POST', body: JSON.stringify(book),
  }),
  updateBook: (id: string, book: Partial<Book>) => request<Book>(`/books/${id}`, {
    method: 'PATCH', body: JSON.stringify(book),
  }),
  archiveBook: (id: string) => request<void>(`/books/${id}`, { method: 'DELETE' }),
  checkout: (key: string, items: Array<{ book_id: string; quantity: number }>, payments: Array<{ method: 'cash' | 'card'; amount: string; cash_received?: string }>) => request<Sale>('/sales', {
    method: 'POST',
    headers: { 'Idempotency-Key': key },
    body: JSON.stringify({ items, payments }),
  }),
  sales: (page = 1) => request<PageSales>(`/sales?page=${page}&page_size=50`),
  sale: (id: string) => request<Sale>(`/sales/${id}`),
  returnSale: (id: string, reason: string, items: Array<{ sale_item_id: string; quantity: number; restock: boolean }>) => request<{ id: string; refund_total: string }>(`/sales/${id}/returns`, {
    method: 'POST', body: JSON.stringify({ reason, items }),
  }),
  movements: () => request<StockMovement[]>('/inventory/movements?page_size=50'),
  adjustStock: (book_id: string, quantity_delta: number, reason: string) => request<StockMovement>('/inventory/adjustments', {
    method: 'POST', body: JSON.stringify({ book_id, quantity_delta, reason }),
  }),
  dailyReport: () => request<DailyReport>('/reports/daily-sales'),
  lowStock: (threshold = 3) => request<Book[]>(`/reports/low-stock?threshold=${threshold}`),
}