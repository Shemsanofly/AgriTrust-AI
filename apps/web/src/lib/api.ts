import { currentLang } from '../i18n'

const BASE = import.meta.env.VITE_API_URL ?? '/api'
const TOKENS_KEY = 'shamba.tokens'

type Tokens = { access_token: string; refresh_token: string }

export class ApiError extends Error {
  status: number
  code: string
  constructor(status: number, code: string) {
    super(code)
    this.status = status
    this.code = code
  }
}

export function getTokens(): Tokens | null {
  try {
    const raw = localStorage.getItem(TOKENS_KEY)
    return raw ? (JSON.parse(raw) as Tokens) : null
  } catch {
    return null
  }
}

export function setTokens(tokens: Tokens | null) {
  try {
    if (tokens) localStorage.setItem(TOKENS_KEY, JSON.stringify(tokens))
    else localStorage.removeItem(TOKENS_KEY)
  } catch {
    /* storage unavailable (private mode): session-only login */
  }
}

let refreshing: Promise<boolean> | null = null

async function refreshTokens(): Promise<boolean> {
  const tokens = getTokens()
  if (!tokens) return false
  refreshing ??= fetch(`${BASE}/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: tokens.refresh_token }),
  })
    .then(async (r) => {
      if (!r.ok) {
        setTokens(null)
        return false
      }
      const data = await r.json()
      setTokens({ access_token: data.access_token, refresh_token: data.refresh_token })
      return true
    })
    .catch(() => false)
    .finally(() => {
      refreshing = null
    })
  return refreshing
}

export async function api<T = any>(path: string, options: { method?: string; body?: unknown; auth?: boolean } = {}): Promise<T> {
  const { method = 'GET', body, auth = true } = options
  const doFetch = () => {
    const headers: Record<string, string> = { 'Accept-Language': currentLang() }
    if (body !== undefined) headers['Content-Type'] = 'application/json'
    const tokens = getTokens()
    if (auth && tokens) headers.Authorization = `Bearer ${tokens.access_token}`
    return fetch(`${BASE}${path}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) })
  }
  let res: Response
  try {
    res = await doFetch()
  } catch {
    throw new ApiError(0, 'offline')
  }
  if (res.status === 401 && auth && getTokens() && (await refreshTokens())) {
    res = await doFetch()
  }
  if (res.status === 204) return undefined as T
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    const detail = data?.detail
    const code = typeof detail === 'string' ? detail : res.status === 422 ? 'validation' : 'unknown'
    throw new ApiError(res.status, code)
  }
  return data as T
}

export const apiUrl = (path: string) => `${BASE}${path}`
