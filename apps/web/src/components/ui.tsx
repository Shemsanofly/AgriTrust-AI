import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

export function Card({ title, children, actions, className = '' }: { title?: ReactNode; children: ReactNode; actions?: ReactNode; className?: string }) {
  return (
    <section className={`rounded-2xl border border-stone-200 bg-white p-4 shadow-sm ${className}`}>
      {(title || actions) && (
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          {title && <h2 className="text-base font-semibold text-stone-900">{title}</h2>}
          {actions}
        </div>
      )}
      {children}
    </section>
  )
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'danger' | 'ghost'; busy?: boolean }

export function Button({ variant = 'primary', busy, className = '', children, disabled, ...rest }: ButtonProps) {
  const styles = {
    primary: 'bg-brand-700 text-white hover:bg-brand-800',
    secondary: 'bg-white text-stone-800 border border-stone-300 hover:bg-stone-50',
    danger: 'bg-red-600 text-white hover:bg-red-700',
    ghost: 'text-brand-800 hover:bg-brand-50',
  }[variant]
  return (
    <button
      className={`inline-flex min-h-10 items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${styles} ${className}`}
      disabled={disabled || busy}
      {...rest}
    >
      {busy && <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />}
      {children}
    </button>
  )
}

const TONES = {
  green: 'bg-green-100 text-green-800',
  amber: 'bg-amber-100 text-amber-800',
  red: 'bg-red-100 text-red-800',
  blue: 'bg-sky-100 text-sky-800',
  stone: 'bg-stone-100 text-stone-700',
  purple: 'bg-purple-100 text-purple-800',
}

export function Badge({ tone = 'stone', children }: { tone?: keyof typeof TONES; children: ReactNode }) {
  return <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ${TONES[tone]}`}>{children}</span>
}

export function RiskBadge({ level }: { level?: string | null }) {
  const { t } = useTranslation()
  if (!level) return null
  const tone = level === 'LOW' ? 'green' : level === 'MEDIUM' ? 'amber' : level === 'HIGH' ? 'red' : 'stone'
  return <Badge tone={tone}>{t(`risk.${level}`)}</Badge>
}

export function VerifyBadge({ status }: { status?: string | null }) {
  const { t } = useTranslation()
  if (!status) return null
  const map: Record<string, [keyof typeof TONES, string]> = {
    VERIFIED: ['green', '✅'],
    MISMATCH: ['red', '⚠️'],
    NOT_ANCHORED: ['stone', '⏳'],
    PARTIAL: ['amber', '⏳'],
  }
  const [tone, icon] = map[status] ?? ['stone', '']
  return (
    <Badge tone={tone}>
      {icon} {t(`verify.status.${status}`)}
    </Badge>
  )
}

export function StatusBadge({ status }: { status: string }) {
  const { t } = useTranslation()
  const good = ['APPROVED', 'ACTIVE', 'SALE_CONFIRMED', 'PAID', 'DISBURSED', 'CLOSED', 'DELIVERED', 'RELEASED']
  const bad = ['DECLINED', 'REJECTED', 'CANCELLED', 'REVOKED', 'EXPIRED']
  const tone = good.includes(status) ? 'green' : bad.includes(status) ? 'red' : 'blue'
  return <Badge tone={tone}>{t(`status.${status}`, { defaultValue: status })}</Badge>
}

/** Every simulated component is labelled in the UI (README definition of done). */
export function SimulatedTag({ label }: { label?: string }) {
  const { t } = useTranslation()
  return (
    <span title={t('common.simulatedHint')} className="inline-flex items-center rounded border border-dashed border-purple-400 bg-purple-50 px-1.5 py-0.5 text-[10px] font-bold tracking-wide text-purple-700 uppercase">
      {label ?? t('common.simulated')}
    </span>
  )
}

export function Field({ label, children, hint }: { label: ReactNode; children: ReactNode; hint?: ReactNode }) {
  return (
    <label className="block">
      <span className="label">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-stone-500">{hint}</span>}
    </label>
  )
}

export function ErrorNote({ text }: { text?: string | null }) {
  if (!text) return null
  return <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">{text}</p>
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="rounded-lg bg-stone-50 px-3 py-6 text-center text-sm text-stone-500">{children}</p>
}

export function Loading() {
  const { t } = useTranslation()
  return <p className="py-8 text-center text-sm text-stone-500">{t('common.loading')}</p>
}

export function Stat({ label, value, sub }: { label: ReactNode; value: ReactNode; sub?: ReactNode }) {
  return (
    <div className="rounded-xl bg-stone-50 p-3">
      <div className="text-xs text-stone-500">{label}</div>
      <div className="mt-1 text-xl font-semibold text-stone-900">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-stone-500">{sub}</div>}
    </div>
  )
}

export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: { id: T; label: ReactNode }[]; value: T; onChange: (id: T) => void }) {
  return (
    <div className="-mx-1 flex gap-1 overflow-x-auto pb-1" role="tablist">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          role="tab"
          aria-selected={tab.id === value}
          onClick={() => onChange(tab.id)}
          className={`shrink-0 rounded-full px-3 py-1.5 text-sm font-medium ${tab.id === value ? 'bg-brand-800 text-white' : 'bg-white text-stone-700 border border-stone-200'}`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  )
}
