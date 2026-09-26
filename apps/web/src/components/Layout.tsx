import { Bell, ChevronRight, LogOut, Menu, UserRound, WifiOff, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { NAV, type NavItem } from '../app/nav'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { LanguageSwitcher } from './LanguageSwitcher'
import { Notice, cx } from './ui'

export function BrandMark({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <rect width="32" height="32" rx="7" fill="#1f5134" />
      <path d="M16 25V13" stroke="#f7eacb" strokeWidth="2.2" strokeLinecap="round" />
      <path d="M16 15.5c0-4.4 3.3-7.5 7.8-7.5 0 4.4-3.4 7.5-7.8 7.5ZM16 19c0-3.9-2.9-6.5-6.8-6.5 0 3.9 2.9 6.5 6.8 6.5Z" fill="#e2a72e" />
    </svg>
  )
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

/** Count of open alerts, refreshed on navigation (no background polling on 2G). */
function useOpenAlerts() {
  const location = useLocation()
  const [count, setCount] = useState(0)
  useEffect(() => {
    let cancelled = false
    api<{ resolved_at: string | null }[]>('/alerts')
      .then((rows) => !cancelled && setCount(rows.filter((r) => !r.resolved_at).length))
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [location.pathname])
  return count
}

function NavEntry({ item, alerts, onClick }: { item: NavItem; alerts: number; onClick?: () => void }) {
  const { t } = useTranslation()
  const Icon = item.icon
  return (
    <NavLink
      to={item.to}
      end={item.to === '/'}
      onClick={onClick}
      className={({ isActive }) =>
        cx(
          'flex min-h-10 items-center gap-3 rounded-md px-3 text-sm font-medium',
          isActive ? 'bg-forest-800 text-white' : 'text-ink-soft hover:bg-sunken hover:text-ink',
        )
      }
    >
      <Icon className="size-[18px] shrink-0" aria-hidden />
      <span className="flex-1 truncate">{t(item.key)}</span>
      {item.badge === 'alerts' && alerts > 0 && <span className="num rounded bg-harvest-500 px-1.5 text-xs font-semibold text-forest-950">{alerts}</span>}
    </NavLink>
  )
}

const OTHER_TITLES: Record<string, string> = { alerts: 'nav.alerts', profile: 'nav.profile', verify: 'verify.viewRecord', scan: 'verify.scanTitle' }

export function Layout() {
  const { t } = useTranslation()
  const { user, logout, newDevice, dismissNewDevice } = useAuth()
  const online = useOnline()
  const alerts = useOpenAlerts()
  const location = useLocation()
  const [moreOpen, setMoreOpen] = useState(false)
  useEffect(() => setMoreOpen(false), [location.pathname])
  if (!user) return null

  const items = NAV[user.role]
  const tabItems = items.length > 5 ? items.slice(0, 4) : items
  const moreItems = items.length > 5 ? items.slice(4) : []
  const current = [...items].sort((a, b) => b.to.length - a.to.length).find((i) => (i.to === '/' ? location.pathname === '/' : location.pathname.startsWith(i.to)))
  const hasAlertsNav = items.some((i) => i.badge === 'alerts') || user.role === 'FARMER'

  return (
    <div className="min-h-dvh lg:pl-64">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col border-r border-line bg-surface lg:flex">
        <Link to="/" className="flex items-center gap-2.5 px-5 pt-5 pb-4">
          <BrandMark className="size-8" />
          <div className="text-[15px] leading-tight font-semibold text-ink">{t('app.name')}</div>
        </Link>
        <div className="eyebrow px-5 pt-2 pb-2">{t(`roles.${user.role}`)}</div>
        <nav className="flex-1 space-y-0.5 overflow-y-auto px-3" aria-label={t('nav.main')}>
          {items.map((item) => (
            <NavEntry key={item.to} item={item} alerts={alerts} />
          ))}
        </nav>
        <div className="space-y-3 border-t border-line p-3">
          <LanguageSwitcher />
          <NavLink
            to="/profile"
            className={({ isActive }) => cx('flex items-center gap-3 rounded-md p-2 hover:bg-sunken', isActive && 'bg-sunken')}
          >
            <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-forest-100 text-sm font-semibold text-forest-800">
              {user.full_name.slice(0, 1)}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium text-ink">{user.full_name}</span>
              <span className="block truncate text-xs text-muted">{t('nav.profile')}</span>
            </span>
            <ChevronRight className="size-4 text-muted" aria-hidden />
          </NavLink>
          <button onClick={logout} className="flex min-h-10 w-full items-center gap-3 rounded-md px-3 text-sm text-ink-soft hover:bg-sunken">
            <LogOut className="size-[18px]" aria-hidden /> {t('auth.logout')}
          </button>
        </div>
      </aside>

      {/* Phone / tablet top bar */}
      <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-line bg-surface/95 px-4 backdrop-blur lg:hidden">
        <Link to="/" aria-label={t('app.name')}>
          <BrandMark className="size-7" />
        </Link>
        <div className="min-w-0 flex-1 truncate text-[15px] font-semibold">{current ? t(current.key) : t(OTHER_TITLES[location.pathname.split('/')[1]] ?? 'app.name')}</div>
        <LanguageSwitcher compact />
        {!hasAlertsNav ? null : (
          <Link to="/alerts" className="relative flex size-10 items-center justify-center rounded-md text-ink-soft hover:bg-sunken" aria-label={t('alerts.aria', { count: alerts })}>
            <Bell className="size-5" aria-hidden />
            {alerts > 0 && <span className="num absolute top-1.5 right-1 rounded bg-harvest-500 px-1 text-[10px] font-bold text-forest-950">{alerts}</span>}
          </Link>
        )}
        <Link to="/profile" className="flex size-10 items-center justify-center rounded-md text-ink-soft hover:bg-sunken" aria-label={t('nav.profile')}>
          <UserRound className="size-5" aria-hidden />
        </Link>
      </header>

      {/* Desktop utility bar */}
      <div className="hidden h-12 items-center justify-end gap-2 px-8 lg:flex">
        {hasAlertsNav && (
          <Link to="/alerts" className="relative flex items-center gap-2 rounded-md px-3 py-1.5 text-sm text-ink-soft hover:bg-sunken">
            <Bell className="size-4" aria-hidden />
            {t('nav.alerts')}
            {alerts > 0 && <span className="num rounded bg-harvest-500 px-1.5 text-xs font-semibold text-forest-950">{alerts}</span>}
          </Link>
        )}
      </div>

      {!online && (
        <div className="flex items-center justify-center gap-2 bg-warn-100 px-4 py-2 text-center text-sm text-warn-700" role="status">
          <WifiOff className="size-4" aria-hidden /> {t('common.offline')}
        </div>
      )}

      <main className="mx-auto max-w-6xl px-4 pt-4 pb-28 sm:px-6 lg:px-8 lg:pt-0 lg:pb-12">
        {newDevice && (
          <Notice
            tone="warning"
            className="mb-4"
            title={t('security.newDeviceTitle')}
            action={
              <button onClick={dismissNewDevice} className="flex size-8 items-center justify-center rounded hover:bg-black/5" aria-label={t('common.close')}>
                <X className="size-4" aria-hidden />
              </button>
            }
          >
            {t('security.newDeviceBody')}{' '}
            <Link to="/profile" className="font-medium underline">
              {t('security.reviewDevices')}
            </Link>
          </Notice>
        )}
        <Outlet />
      </main>

      {/* Phone tab bar */}
      <nav className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-surface pb-[env(safe-area-inset-bottom)] lg:hidden" aria-label={t('nav.main')}>
        <div className="flex">
          {tabItems.map((item) => {
            const Icon = item.icon
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  cx('relative flex min-h-16 flex-1 flex-col items-center justify-center gap-1 px-1 text-[11px] font-medium', isActive ? 'text-forest-800' : 'text-muted')
                }
              >
                {({ isActive }) => (
                  <>
                    {isActive && <span className="absolute top-0 h-0.5 w-8 rounded-full bg-forest-800" />}
                    <Icon className="size-[22px]" aria-hidden strokeWidth={isActive ? 2.2 : 1.8} />
                    <span className="max-w-full truncate">{t(item.key)}</span>
                  </>
                )}
              </NavLink>
            )
          })}
          {moreItems.length > 0 && (
            <button onClick={() => setMoreOpen(true)} className="flex min-h-16 flex-1 flex-col items-center justify-center gap-1 text-[11px] font-medium text-muted">
              <Menu className="size-[22px]" aria-hidden />
              {t('nav.more')}
            </button>
          )}
        </div>
      </nav>

      {moreOpen && (
        <div className="fixed inset-0 z-40 bg-forest-950/40 lg:hidden" onClick={() => setMoreOpen(false)}>
          <div className="absolute inset-x-0 bottom-0 rounded-t-xl bg-surface p-3 pb-[calc(env(safe-area-inset-bottom)+12px)]" onClick={(e) => e.stopPropagation()}>
            <div className="space-y-0.5">
              {moreItems.map((item) => (
                <NavEntry key={item.to} item={item} alerts={alerts} />
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

