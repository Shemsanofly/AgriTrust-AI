import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import i18n, { type Lang } from '../i18n'
import { api, getTokens, setTokens } from './api'
import { biometricSignIn } from './biometric'

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

type LoginResult = { access_token: string; refresh_token: string; user: User; new_device?: boolean }

type AuthState = {
  user: User | null
  loading: boolean
  /** True right after signing in on a device this account has not used before. */
  newDevice: boolean
  hasPasskey: boolean
  login: (phone: string, pin: string) => Promise<void>
  loginWithBiometric: (phone: string) => Promise<void>
  completeLogin: (data: LoginResult) => void
  logout: () => Promise<void>
  setLanguage: (lang: Lang) => Promise<void>
  refreshSecurity: () => Promise<void>
  dismissNewDevice: () => void
}

const AuthContext = createContext<AuthState | null>(null)
const LAST_PHONE = 'shamba.lastPhone'

export function rememberedPhone(): string {
  try {
    return localStorage.getItem(LAST_PHONE) ?? ''
  } catch {
    return ''
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [newDevice, setNewDevice] = useState(false)
  const [hasPasskey, setHasPasskey] = useState(false)

  const refreshSecurity = useCallback(async () => {
    try {
      const sec = await api<{ passkeys: unknown[] }>('/me/security')
      setHasPasskey(sec.passkeys.length > 0)
    } catch {
      setHasPasskey(false)
    }
  }, [])

  useEffect(() => {
    if (!getTokens()) {
      setLoading(false)
      return
    }
    api<User>('/me')
      .then((u) => {
        setUser(u)
        i18n.changeLanguage(u.language)
        refreshSecurity()
      })
      .catch(() => setTokens(null))
      .finally(() => setLoading(false))
  }, [refreshSecurity])

  const completeLogin = useCallback(
    (data: LoginResult) => {
      setTokens({ access_token: data.access_token, refresh_token: data.refresh_token })
      setUser(data.user)
      setNewDevice(Boolean(data.new_device))
      try {
        localStorage.setItem(LAST_PHONE, data.user.phone)
      } catch {
        /* ignore */
      }
      // The account's saved preference wins, so a shared phone opens in each user's own language.
      i18n.changeLanguage(data.user.language)
      refreshSecurity()
    },
    [refreshSecurity],
  )

  const login = useCallback(
    async (phone: string, pin: string) => {
      completeLogin(await api<LoginResult>('/auth/login', { method: 'POST', body: { phone, pin }, auth: false }))
    },
    [completeLogin],
  )

  const loginWithBiometric = useCallback(
    async (phone: string) => {
      completeLogin(await biometricSignIn(phone))
    },
    [completeLogin],
  )

  const logout = useCallback(async () => {
    const tokens = getTokens()
    if (tokens) await api('/auth/logout', { method: 'POST', body: { refresh_token: tokens.refresh_token }, auth: false }).catch(() => {})
    setTokens(null)
    setUser(null)
    setHasPasskey(false)
    setNewDevice(false)
  }, [])

  const setLanguage = useCallback(
    async (lang: Lang) => {
      await i18n.changeLanguage(lang)
      if (user && user.language !== lang) {
        try {
          setUser(await api<User>('/me', { method: 'PATCH', body: { language: lang } }))
        } catch {
          /* offline: the UI language still changes; the account keeps the old preference */
        }
      }
    },
    [user],
  )

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        newDevice,
        hasPasskey,
        login,
        loginWithBiometric,
        completeLogin,
        logout,
        setLanguage,
        refreshSecurity,
        dismissNewDevice: () => setNewDevice(false),
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth outside AuthProvider')
  return ctx
}
