import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { NavLink, Outlet } from 'react-router-dom'
import { useAuth, type Role } from '../lib/auth'
import { LanguageSwitcher } from './LanguageSwitcher'

const NAV: Record<Role, { to: string; key: string; icon: string }[]> = {
  FARMER: [
    { to: '/', key: 'nav.shamba', icon: '🌱' },
    { to: '/batches', key: 'nav.ghala', icon: '🏚️' },
    { to: '/orders', key: 'nav.orders', icon: '🧺' },
    { to: '/kifedha', key: 'nav.kifedha', icon: '💰' },
  ],
  BUYER: [
    { to: '/', key: 'nav.market', icon: '🧺' },
    { to: '/orders', key: 'nav.orders', icon: '📦' },
  ],
  WAREHOUSE_OPERATOR: [
    { to: '/', key: 'nav.warehouse', icon: '🏚️' },
    { to: '/orders', key: 'nav.releases', icon: '📦' },
  ],
  LENDER: [{ to: '/', key: 'nav.applications', icon: '💰' }],
  INSURER: [{ to: '/', key: 'nav.policies', icon: '🛡️' }],
  ADMIN: [{ to: '/', key: 'nav.admin', icon: '🛠️' }],
}

function useOnline() {
  const [online, setOnline] = useState(navigator.onLine)
  useEffect(() => {
    const on = () => setOnline(true)
    const off = () => setOnline(false)
    window.addEventListener('online', on)
    window.addEventListener('offline', off)
    return () => {
      window.removeEventListener('online', on)
      window.removeEventListener('offline', off)
    }
  }, [])
  return online
}

export function Layout() {
  const { t } = useTranslation()
  const { user, logout } = useAuth()
  const online = useOnline()
  if (!user) return null
  const items = NAV[user.role]

  return (
    <div className="min-h-screen pb-20 sm:pb-6">
      <header className="sticky top-0 z-30 bg-brand-900 text-white shadow">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-3 px-4 py-3">
          <div className="min-w-0">
            <div className="truncate text-base font-bold">🌱 {t('app.name')}</div>
            <div className="truncate text-xs text-white/70">
              {user.full_name} · {t(`roles.${user.role}`)}
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <LanguageSwitcher tone="dark" />
            <button onClick={logout} className="rounded-full px-2 py-1 text-xs text-white/80 hover:bg-white/10">
              {t('auth.logout')}
            </button>
          </div>
        </div>
        <nav className="mx-auto hidden max-w-5xl gap-1 px-4 pb-2 sm:flex">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end
              className={({ isActive }) => `rounded-full px-3 py-1.5 text-sm ${isActive ? 'bg-white text-brand-900' : 'text-white/85 hover:bg-white/10'}`}
            >
              {item.icon} {t(item.key)}
            </NavLink>
          ))}
        </nav>
      </header>
      {!online && <div className="bg-amber-100 px-4 py-2 text-center text-sm text-amber-900">📴 {t('common.offline')}</div>}
      <main className="mx-auto max-w-5xl px-4 py-4">
        <Outlet />
      </main>
      {items.length > 1 && (
        <nav className="fixed inset-x-0 bottom-0 z-30 flex border-t border-stone-200 bg-white sm:hidden">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end
              className={({ isActive }) => `flex flex-1 flex-col items-center py-2 text-[11px] ${isActive ? 'text-brand-800 font-semibold' : 'text-stone-500'}`}
            >
              <span className="text-lg" aria-hidden>
                {item.icon}
              </span>
              {t(item.key)}
            </NavLink>
          ))}
        </nav>
      )}
    </div>
  )
}
