/* Shambani → Kifedha UI kit. One place for spacing, colour and state patterns so every
   screen reads the same. Prefer these over ad-hoc markup in features. */
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  CircleAlert,
  CircleDashed,
  Info,
  Loader2,
  ShieldAlert,
  ShieldCheck,
  X,
  type LucideIcon,
} from 'lucide-react'
import { createContext, useCallback, useContext, useEffect, useId, useRef, useState, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

const cx = (...parts: unknown[]) => parts.filter((p) => typeof p === 'string' && p).join(' ')
export { cx }

/* ------------------------------------------------------------------ layout */

export function PageHeader({ title, subtitle, eyebrow, actions }: { title: ReactNode; subtitle?: ReactNode; eyebrow?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        {eyebrow && <div className="eyebrow mb-1">{eyebrow}</div>}
        <h1 className="text-[22px] leading-7 font-semibold tracking-tight text-ink sm:text-2xl">{title}</h1>
        {subtitle && <p className="mt-1 max-w-2xl text-sm text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  )
}

export function Card({
  title,
  subtitle,
  children,
  actions,
  className = '',
  padded = true,
  as: Tag = 'section',
}: {
  title?: ReactNode
  subtitle?: ReactNode
  children: ReactNode
  actions?: ReactNode
  className?: string
  padded?: boolean
  as?: 'section' | 'div' | 'article'
}) {
  return (
    <Tag className={cx('rounded-(--radius-card) border border-line bg-surface', className)}>
      {(title || actions) && (
        <div className={cx('flex flex-wrap items-start justify-between gap-x-3 gap-y-2', padded ? 'px-4 pt-4 sm:px-5' : 'px-4 pt-4')}>
          <div className="min-w-0">
            {title && <h2 className="text-[15px] font-semibold text-ink">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-[13px] text-muted">{subtitle}</p>}
          </div>
          {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
        </div>
      )}
      <div className={cx(padded && 'p-4 sm:px-5', padded && (title || actions) && 'pt-3')}>{children}</div>
    </Tag>
  )
}

/** A titled group inside a page without a box around it. */
export function Section({ title, actions, children, className = '' }: { title: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={className}>
      <div className="mb-2.5 flex items-center justify-between gap-2">
        <h2 className="text-[15px] font-semibold text-ink">{title}</h2>
        {actions}
      </div>
      {children}
    </section>
  )
}

export function Divider() {
  return <hr className="my-4 border-line" />
}

/* ------------------------------------------------------------------ actions */

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost' | 'gold'
  size?: 'md' | 'sm' | 'lg'
  busy?: boolean
  icon?: LucideIcon
}

export function Button({ variant = 'primary', size = 'md', busy, icon: Icon, className = '', children, disabled, type = 'button', ...rest }: ButtonProps) {
  const styles = {
    primary: 'bg-forest-800 text-white hover:bg-forest-900 active:bg-forest-950',
    gold: 'bg-harvest-500 text-forest-950 hover:bg-[#d49a22]',
    secondary: 'border border-line-strong bg-surface text-ink hover:bg-sunken',
    danger: 'border border-danger-700/30 bg-surface text-danger-700 hover:bg-danger-100',
    ghost: 'text-forest-800 hover:bg-forest-50',
  }[variant]
  const sizes = { sm: 'min-h-9 px-3 text-[13px] gap-1.5', md: 'min-h-11 px-4 text-sm gap-2', lg: 'min-h-12 px-5 text-[15px] gap-2' }[size]
  return (
    <button
      type={type}
      className={cx(
        'inline-flex items-center justify-center rounded-md font-medium whitespace-nowrap transition-colors disabled:cursor-not-allowed disabled:opacity-50',
        styles,
        sizes,
        className,
      )}
      disabled={disabled || busy}
      aria-busy={busy || undefined}
      {...rest}
    >
      {busy ? <Loader2 className="size-4 animate-spin" aria-hidden /> : Icon ? <Icon className="size-4 shrink-0" aria-hidden /> : null}
      {children}
    </button>
  )
}

/* ------------------------------------------------------------------ status */

const TONES = {
  green: 'bg-forest-100 text-forest-800',
  gold: 'bg-harvest-100 text-harvest-800',
  amber: 'bg-warn-100 text-warn-700',
  red: 'bg-danger-100 text-danger-700',
  blue: 'bg-info-100 text-info-700',
  earth: 'bg-earth-100 text-earth-800',
  stone: 'bg-sunken text-ink-soft',
}
export type Tone = keyof typeof TONES

export function Badge({ tone = 'stone', icon: Icon, children, className = '' }: { tone?: Tone; icon?: LucideIcon; children: ReactNode; className?: string }) {
  return (
    <span className={cx('inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-medium whitespace-nowrap', TONES[tone], className)}>
      {Icon && <Icon className="size-3.5" aria-hidden />}
      {children}
    </span>
  )
}

export const RISK_TONE: Record<string, Tone> = { LOW: 'green', MEDIUM: 'amber', HIGH: 'red', UNKNOWN: 'stone' }
const RISK_ICON: Record<string, LucideIcon> = { LOW: CheckCircle2, MEDIUM: AlertTriangle, HIGH: ShieldAlert, UNKNOWN: CircleDashed }

/** Risk is never colour-only: icon + word + colour. */
export function RiskBadge({ level, prefix }: { level?: string | null; prefix?: ReactNode }) {
  const { t } = useTranslation()
  if (!level) return null
  return (
    <Badge tone={RISK_TONE[level] ?? 'stone'} icon={RISK_ICON[level] ?? CircleDashed}>
      {prefix}
      {t(`risk.${level}`)}
    </Badge>
  )
}

/** Three-step LOW / MEDIUM / HIGH scale with the current level marked. */
export function RiskScale({ level }: { level: string }) {
  const { t } = useTranslation()
  const steps = ['LOW', 'MEDIUM', 'HIGH']
  const fill = { LOW: 'bg-forest-700', MEDIUM: 'bg-harvest-500', HIGH: 'bg-danger-700' } as Record<string, string>
  return (
    <div className="grid grid-cols-3 gap-1" role="img" aria-label={t('risk.aria', { level: t(`risk.${level}`) })}>
      {steps.map((s) => (
        <div key={s}>
          <div className={cx('h-1.5 rounded-full', s === level ? fill[s] : 'bg-line')} />
          <div className={cx('mt-1 text-[11px]', s === level ? 'font-semibold text-ink' : 'text-muted')}>{t(`risk.${s}`)}</div>
        </div>
      ))}
    </div>
  )
}

export function VerifyBadge({ status, size = 'sm' }: { status?: string | null; size?: 'sm' | 'md' }) {
  const { t } = useTranslation()
  if (!status) return null
  const map: Record<string, [Tone, LucideIcon]> = {
    VERIFIED: ['green', ShieldCheck],
    MISMATCH: ['red', ShieldAlert],
    NOT_ANCHORED: ['stone', CircleDashed],
    PARTIAL: ['amber', CircleDashed],
  }
  const [tone, icon] = map[status] ?? ['stone', CircleDashed]
  return (
    <Badge tone={tone} icon={icon} className={size === 'md' ? 'px-2 py-1 text-[13px]' : ''}>
      {t(`verify.status.${status}`)}
    </Badge>
  )
}

export function StatusBadge({ status }: { status: string }) {
  const { t } = useTranslation()
  const good = ['FULFILLED', 'APPROVED', 'ACTIVE', 'SALE_CONFIRMED', 'PAID', 'DISBURSED', 'CLOSED', 'DELIVERED', 'IN_STORAGE']
  const bad = ['DECLINED', 'REJECTED', 'CANCELLED', 'REVOKED', 'EXPIRED']
  const waiting = ['OFFERED', 'REQUESTED', 'SUBMITTED', 'UNDER_REVIEW', 'FILED', 'EVIDENCE_ATTACHED', 'HARVESTED']
  const tone: Tone = good.includes(status) ? 'green' : bad.includes(status) ? 'red' : waiting.includes(status) ? 'gold' : 'blue'
  return <Badge tone={tone}>{t(`status.${status}`, { defaultValue: status })}</Badge>
}

/** Every simulated component is labelled in the UI (README definition of done). */
export function SimulatedTag({ label }: { label?: string }) {
  const { t } = useTranslation()
  return (
    <span
      title={t('common.simulatedHint')}
      className="inline-flex items-center rounded border border-dashed border-earth-700/50 px-1.5 py-px text-[10px] font-semibold tracking-wide text-earth-800 uppercase"
    >
      {label ?? t('common.simulated')}
    </span>
  )
}

/* ------------------------------------------------------------------ notices */

const NOTICE = {
  info: ['bg-info-100 text-info-700', Info],
  success: ['bg-forest-100 text-forest-900', CheckCircle2],
  warning: ['bg-warn-100 text-warn-700', AlertTriangle],
  danger: ['bg-danger-100 text-danger-700', CircleAlert],
  neutral: ['bg-sunken text-ink-soft', Info],
} as const

export function Notice({ tone = 'info', title, children, action, className = '' }: { tone?: keyof typeof NOTICE; title?: ReactNode; children?: ReactNode; action?: ReactNode; className?: string }) {
  const [styles, Icon] = NOTICE[tone]
  return (
    <div className={cx('flex gap-3 rounded-md px-3.5 py-3 text-sm', styles, className)} role={tone === 'danger' ? 'alert' : undefined}>
      <Icon className="mt-0.5 size-4 shrink-0" aria-hidden />
      <div className="min-w-0 flex-1">
        {title && <div className="font-semibold">{title}</div>}
        {children && <div className={cx(title && 'mt-0.5', 'opacity-95')}>{children}</div>}
      </div>
      {action && <div className="shrink-0 self-center">{action}</div>}
    </div>
  )
}

export function ErrorNote({ text }: { text?: string | null }) {
  if (!text) return null
  return <Notice tone="danger">{text}</Notice>
}

export function EmptyState({ icon: Icon, title, body, action, compact }: { icon?: LucideIcon; title: ReactNode; body?: ReactNode; action?: ReactNode; compact?: boolean }) {
  return (
    <div className={cx('flex flex-col items-center text-center', compact ? 'px-4 py-6' : 'px-6 py-10')}>
      {Icon && (
        <span className="mb-3 flex size-10 items-center justify-center rounded-full bg-sunken text-muted">
          <Icon className="size-5" aria-hidden />
        </span>
      )}
      <p className="text-sm font-medium text-ink">{title}</p>
      {body && <p className="mt-1 max-w-sm text-[13px] text-muted">{body}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

/** Back-compat alias used by older screens. */
export function Empty({ children }: { children: ReactNode }) {
  return <EmptyState compact title={children} />
}

export function ErrorState({ text, onRetry }: { text: string; onRetry?: () => void }) {
  const { t } = useTranslation()
  return (
    <EmptyState
      icon={CircleAlert}
      title={t('common.loadFailed')}
      body={text}
      action={onRetry && <Button variant="secondary" size="sm" onClick={onRetry}>{t('common.retry')}</Button>}
    />
  )
}

export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={cx('animate-pulse rounded bg-sunken', className)} aria-hidden />
}

export function Loading({ rows = 3 }: { rows?: number }) {
  const { t } = useTranslation()
  return (
    <div className="space-y-3 py-2" role="status" aria-live="polite">
      <span className="sr-only">{t('common.loading')}</span>
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className={cx('h-16', i === 0 && 'h-24')} />
      ))}
    </div>
  )
}

/* ------------------------------------------------------------------ data */

export function Stat({ label, value, sub, icon: Icon, tone }: { label: ReactNode; value: ReactNode; sub?: ReactNode; icon?: LucideIcon; tone?: Tone }) {
  return (
    <div className="min-w-0">
      <div className="flex items-center gap-1.5 text-[13px] text-muted">
        {Icon && <Icon className="size-4 shrink-0 self-start mt-px" aria-hidden />}
        <span className="leading-snug">{label}</span>
      </div>
      <div className={cx('num mt-1 text-xl font-semibold tracking-tight', tone === 'red' ? 'text-danger-700' : tone === 'amber' ? 'text-warn-700' : 'text-ink')}>{value}</div>
      {sub && <div className="mt-0.5 text-xs text-muted">{sub}</div>}
    </div>
  )
}

/** A row of stats separated by hairlines (avoids a grid of identical cards). */
export function StatStrip({ children, cols = 4 }: { children: ReactNode; cols?: 2 | 3 | 4 }) {
  const grid = { 2: 'grid-cols-2', 3: 'grid-cols-2 sm:grid-cols-3', 4: 'grid-cols-2 lg:grid-cols-4' }[cols]
  return (
    <div className={cx('grid gap-px overflow-hidden rounded-(--radius-card) border border-line bg-line', grid)}>
      {(Array.isArray(children) ? children : [children]).filter(Boolean).map((child, i) => (
        <div key={i} className="bg-surface px-4 py-3.5">
          {child}
        </div>
      ))}
    </div>
  )
}

export function KeyValues({ items, cols = 2 }: { items: [ReactNode, ReactNode][]; cols?: 1 | 2 | 3 }) {
  const grid = { 1: '', 2: 'sm:grid-cols-2', 3: 'sm:grid-cols-3' }[cols]
  return (
    <dl className={cx('grid gap-x-6 gap-y-3', grid)}>
      {items.map(([k, v], i) => (
        <div key={i} className="min-w-0">
          <dt className="text-xs text-muted">{k}</dt>
          <dd className="mt-0.5 text-sm font-medium break-words text-ink">{v}</dd>
        </div>
      ))}
    </dl>
  )
}

export function ProgressBar({ value, max = 100, tone = 'green', label }: { value: number; max?: number; tone?: 'green' | 'gold' | 'red'; label?: string }) {
  const pct = Math.max(0, Math.min(100, (value / (max || 1)) * 100))
  const color = { green: 'bg-forest-700', gold: 'bg-harvest-500', red: 'bg-danger-700' }[tone]
  return (
    <div className="h-1.5 overflow-hidden rounded-full bg-sunken" role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100} aria-label={label}>
      <div className={cx('h-full rounded-full', color)} style={{ width: `${pct}%` }} />
    </div>
  )
}

/* ------------------------------------------------------------------ recommendations */

/** An AI recommendation embedded in a workflow: headline, what to do, and why. */
export function Recommendation({
  tone = 'green',
  label,
  headline,
  reasons,
  meta,
  children,
  icon: Icon,
}: {
  tone?: 'green' | 'amber' | 'red' | 'blue'
  label: ReactNode
  headline: ReactNode
  reasons?: ReactNode[]
  meta?: ReactNode
  children?: ReactNode
  icon?: LucideIcon
}) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(true)
  const id = useId()
  const accent = { green: 'text-forest-700', amber: 'text-warn-700', red: 'text-danger-700', blue: 'text-info-700' }[tone]
  const bg = { green: 'bg-forest-50', amber: 'bg-warn-100/60', red: 'bg-danger-100/70', blue: 'bg-info-100/60' }[tone]
  return (
    <section className={cx('rounded-(--radius-card) border border-line', bg)} aria-live="polite">
      <div className="p-4 sm:p-5">
        <div className={cx('flex items-center gap-1.5 text-[13px] font-semibold', accent)}>
          {Icon && <Icon className="size-4" aria-hidden />}
          {label}
        </div>
        <p className="mt-1.5 text-lg leading-snug font-semibold text-ink sm:text-xl">{headline}</p>
        {children && <div className="mt-3">{children}</div>}
      </div>
      {reasons && reasons.length > 0 && (
        <div className="border-t border-line/70 px-4 py-3 sm:px-5">
          <button type="button" className="flex w-full items-center justify-between text-[13px] font-medium text-ink-soft" aria-expanded={open} aria-controls={id} onClick={() => setOpen((v) => !v)}>
            {t('common.why')}
            <ChevronDown className={cx('size-4 transition-transform', open && 'rotate-180')} aria-hidden />
          </button>
          {open && (
            <ul id={id} className="mt-2 space-y-1.5 text-[13px] text-ink-soft">
              {reasons.map((r, i) => (
                <li key={i} className="flex gap-2">
                  <span className="mt-[7px] size-1 shrink-0 rounded-full bg-muted" aria-hidden />
                  <span>{r}</span>
                </li>
              ))}
            </ul>
          )}
          {meta && <p className="mt-2 text-[11px] text-muted">{meta}</p>}
        </div>
      )}
    </section>
  )
}

/* ------------------------------------------------------------------ forms */

export function Field({ label, children, hint, error, optional }: { label: ReactNode; children: ReactNode; hint?: ReactNode; error?: string | null; optional?: boolean }) {
  const { t } = useTranslation()
  return (
    <label className="block min-w-0">
      <span className="label">
        {label}
        {optional && <span className="ml-1 font-normal text-muted">({t('common.optional')})</span>}
      </span>
      {children}
      {error ? <span className="mt-1 block text-xs text-danger-700">{error}</span> : hint ? <span className="mt-1 block text-xs text-muted">{hint}</span> : null}
    </label>
  )
}

export function Segmented<T extends string>({ options, value, onChange, label }: { options: { id: T; label: ReactNode }[]; value: T; onChange: (v: T) => void; label?: string }) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-md border border-line-strong bg-surface p-0.5">
      {options.map((o) => (
        <button
          key={o.id}
          type="button"
          role="radio"
          aria-checked={o.id === value}
          onClick={() => onChange(o.id)}
          className={cx('min-h-9 rounded px-3 text-[13px] font-medium', o.id === value ? 'bg-forest-800 text-white' : 'text-ink-soft hover:bg-sunken')}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

/** Underlined tabs; scroll horizontally on small screens. */
export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: { id: T; label: ReactNode; count?: number }[]; value: T; onChange: (id: T) => void }) {
  return (
    <div className="-mx-4 overflow-x-auto border-b border-line px-4 sm:mx-0 sm:px-0" role="tablist">
      <div className="flex gap-5">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            role="tab"
            type="button"
            aria-selected={tab.id === value}
            onClick={() => onChange(tab.id)}
            className={cx(
              '-mb-px flex min-h-11 shrink-0 items-center gap-1.5 border-b-2 text-sm font-medium whitespace-nowrap',
              tab.id === value ? 'border-forest-800 text-ink' : 'border-transparent text-muted hover:text-ink',
            )}
          >
            {tab.label}
            {tab.count != null && <span className="rounded bg-sunken px-1.5 text-xs text-muted">{tab.count}</span>}
          </button>
        ))}
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ overlays */

/** Bottom sheet on phones, centred dialog on larger screens. */
export function Dialog({ open, onClose, title, children, footer, wide }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; footer?: ReactNode; wide?: boolean }) {
  const { t } = useTranslation()
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const prev = document.activeElement as HTMLElement | null
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    document.body.classList.add('dialog-open')
    requestAnimationFrame(() => ref.current?.querySelector<HTMLElement>('input, button[data-autofocus], select, textarea')?.focus())
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
      document.body.classList.remove('dialog-open')
      prev?.focus?.()
    }
  }, [open, onClose])
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-forest-950/40 sm:items-center sm:p-6" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div ref={ref} role="dialog" aria-modal="true" aria-label={typeof title === 'string' ? title : undefined} className={cx('max-h-[92vh] w-full overflow-y-auto rounded-t-xl bg-surface shadow-xl sm:rounded-xl', wide ? 'sm:max-w-2xl' : 'sm:max-w-md')}>
        <div className="sticky top-0 flex items-center justify-between gap-3 border-b border-line bg-surface px-5 py-3.5">
          <h2 className="text-base font-semibold">{title}</h2>
          <button type="button" onClick={onClose} className="-mr-2 flex size-9 items-center justify-center rounded-md text-muted hover:bg-sunken" aria-label={t('common.close')}>
            <X className="size-5" aria-hidden />
          </button>
        </div>
        <div className="px-5 py-4">{children}</div>
        {footer && <div className="sticky bottom-0 flex justify-end gap-2 border-t border-line bg-surface px-5 py-3">{footer}</div>}
      </div>
    </div>
  )
}

type Toast = { id: number; tone: 'success' | 'info' | 'warning' | 'danger'; text: ReactNode }
const ToastContext = createContext<(text: ReactNode, tone?: Toast['tone']) => void>(() => {})

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const push = useCallback((text: ReactNode, tone: Toast['tone'] = 'success') => {
    const id = Date.now() + Math.random()
    setToasts((all) => [...all, { id, tone, text }])
    setTimeout(() => setToasts((all) => all.filter((x) => x.id !== id)), 5000)
  }, [])
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 bottom-20 z-[60] flex flex-col items-center gap-2 px-4 lg:bottom-6" aria-live="polite">
        {toasts.map((toast) => (
          <div key={toast.id} className="pointer-events-auto w-full max-w-md shadow-lg">
            <Notice tone={toast.tone} className="border border-line bg-surface">
              {toast.text}
            </Notice>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export const useToast = () => useContext(ToastContext)

/* ------------------------------------------------------------------ misc */

export function IconTile({ icon: Icon, tone = 'green' }: { icon: LucideIcon; tone?: 'green' | 'gold' | 'earth' | 'red' | 'blue' | 'stone' }) {
  const styles = {
    green: 'bg-forest-100 text-forest-800',
    gold: 'bg-harvest-100 text-harvest-800',
    earth: 'bg-earth-100 text-earth-800',
    red: 'bg-danger-100 text-danger-700',
    blue: 'bg-info-100 text-info-700',
    stone: 'bg-sunken text-ink-soft',
  }[tone]
  return (
    <span className={cx('flex size-9 shrink-0 items-center justify-center rounded-md', styles)}>
      <Icon className="size-[18px]" aria-hidden />
    </span>
  )
}

export function Stepper({ steps, current }: { steps: string[]; current: number }) {
  return (
    <ol className="flex items-center gap-1.5" aria-label="progress">
      {steps.map((s, i) => (
        <li key={s} className="flex min-w-0 flex-1 flex-col gap-1">
          <div className={cx('h-1 rounded-full', i <= current ? 'bg-forest-700' : 'bg-line')} />
          <span className={cx('truncate text-[11px]', i === current ? 'font-semibold text-ink' : i < current ? 'text-ink-soft' : 'text-muted')}>{s}</span>
        </li>
      ))}
    </ol>
  )
}
