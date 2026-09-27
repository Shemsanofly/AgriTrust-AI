import { currentLang } from '../i18n'

const BASE = import.meta.env.VITE_API_URL ?? '/api'
const TOKENS_KEY = 'shamba.tokens'

type Tokens = { access_token: string; refresh_token: string }

export class ApiError extends Error {
  status: number
  code: string
  details: Record<string, unknown>
  constructor(status: number, code: string, details: Record<string, unknown> = {}) {
    super(code)
    this.status = status
    this.code = code
    this.details = details
  }
}

/** A random id kept on this device so the server can recognise it (never a hardware id). */
export function deviceId(): string {
  try {
    let id = localStorage.getItem('shamba.device')
    if (!id) {
      id = crypto.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`
      localStorage.setItem('shamba.device', id)
    }
    return id
  } catch {
    return 'no-storage'
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
    headers: { 'Content-Type': 'application/json', 'X-Device-Id': deviceId() },
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

/** Sends a request with the session token, refreshing it once on 401. A FormData body is
 * sent as multipart (file uploads); anything else as JSON. */
async function send(path: string, method: string, body: unknown, auth: boolean): Promise<Response> {
  const doFetch = () => {
    const headers: Record<string, string> = { 'Accept-Language': currentLang(), 'X-Device-Id': deviceId() }
    const form = body instanceof FormData
    if (body !== undefined && !form) headers['Content-Type'] = 'application/json'
    const tokens = getTokens()
    if (auth && tokens) headers.Authorization = `Bearer ${tokens.access_token}`
    return fetch(`${BASE}${path}`, { method, headers, body: body === undefined ? undefined : form ? body : JSON.stringify(body) })
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
  return res
}

async function fail(res: Response): Promise<never> {
  const data = await res.json().catch(() => null)
  const detail = data?.detail
  const code = typeof detail === 'string' ? detail : res.status === 422 ? 'validation' : 'unknown'
  throw new ApiError(res.status, code, data && typeof data === 'object' ? data : {})
}

export async function api<T = any>(path: string, options: { method?: string; body?: unknown; auth?: boolean } = {}): Promise<T> {
  const { method = 'GET', body, auth = true } = options
  const res = await send(path, method, body, auth)
  if (res.status === 204) return undefined as T
  if (!res.ok) return fail(res)
  return (await res.json().catch(() => null)) as T
}

/** A private file (e.g. a crop photo) as a Blob; <img src> can't send the session token. */
export async function apiBlob(path: string): Promise<Blob> {
  const res = await send(path, 'GET', undefined, true)
  if (!res.ok) return fail(res)
  return res.blob()
}

export const apiUrl = (path: string) => `${BASE}${path}`
