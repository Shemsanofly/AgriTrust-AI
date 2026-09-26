import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import i18n, { type Lang } from '../i18n'
import { api, getTokens, setTokens } from './api'

export type Role = 'FARMER' | 'BUYER' | 'WAREHOUSE_OPERATOR' | 'LENDER' | 'INSURER' | 'ADMIN'

export type User = {
  id: number
  phone: string
  full_name: string
  role: Role
  language: Lang
  farmer?: { id: number; public_id: string; display_name: string; region: string; district: string; cooperative?: string }
  buyer?: { id: number; business_name: string; country: string }
  warehouses?: { id: number; public_id: string; name: string; region: string }[]
}

type AuthState = {
  user: User | null
  loading: boolean
  login: (phone: string, pin: string) => Promise<void>
  completeLogin: (data: { access_token: string; refresh_token: string; user: User }) => void
  logout: () => Promise<void>
  setLanguage: (lang: Lang) => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!getTokens()) {
      setLoading(false)
      return
    }
    api<User>('/me')
      .then((u) => {
        setUser(u)
        i18n.changeLanguage(u.language)
      })
      .catch(() => setTokens(null))
      .finally(() => setLoading(false))
  }, [])

  const completeLogin = useCallback((data: { access_token: string; refresh_token: string; user: User }) => {
    setTokens({ access_token: data.access_token, refresh_token: data.refresh_token })
    setUser(data.user)
    // The account's saved preference wins, so a shared phone opens in each user's own language.
    i18n.changeLanguage(data.user.language)
  }, [])

  const login = useCallback(
    async (phone: string, pin: string) => {
      const data = await api('/auth/login', { method: 'POST', body: { phone, pin }, auth: false })
      completeLogin(data)
    },
    [completeLogin],
  )

  const logout = useCallback(async () => {
    const tokens = getTokens()
    if (tokens) await api('/auth/logout', { method: 'POST', body: { refresh_token: tokens.refresh_token }, auth: false }).catch(() => {})
    setTokens(null)
    setUser(null)
  }, [])

  const setLanguage = useCallback(
    async (lang: Lang) => {
      await i18n.changeLanguage(lang)
      if (user && user.language !== lang) {
        try {
          const updated = await api<User>('/me', { method: 'PATCH', body: { language: lang } })
          setUser(updated)
        } catch {
          /* offline: the UI language still changes; the account keeps the old preference */
        }
      }
    },
    [user],
  )

  return <AuthContext.Provider value={{ user, loading, login, completeLogin, logout, setLanguage }}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth outside AuthProvider')
  return ctx
}
