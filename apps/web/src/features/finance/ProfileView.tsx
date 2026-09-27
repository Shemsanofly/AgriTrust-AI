import { AlertTriangle, CheckCircle2, ChevronRight, CloudSun, FileSignature, Gauge, Receipt, Scale, ShoppingBasket, Sprout, Warehouse, Wheat, type LucideIcon } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge, Card, KeyValues, Notice, RiskBadge, RiskScale, cx } from '../../components/ui'
import { useBi, useFormat, type Bi } from '../../lib/hooks'

export type Criterion = {
  key: 'transactions' | 'farm' | 'production' | 'offtake' | 'condition'
  title: Bi
  weight: number
  score: number
  level: 'good' | 'fair' | 'weak'
  findings: { good: boolean; text: Bi }[]
  facts: Record<string, any>
}

export type Profile = {
  farmer_id: string
  display_name: string
  region: string
  generated_at: string
  model_version: string
  risk_band: 'LOW' | 'MEDIUM' | 'HIGH'
  score: number
  positive_factors: Bi[]
  risk_factors: Bi[]
  cash_flow_estimate: {
    next_harvest_month: string | null
    expected_income_range_tzs: [number, number] | null
    expected_yield_kg?: number
    price_per_kg_tzs?: number
    price_source?: string
    monthly?: { month: string; income_tzs: [number, number] }[]
  }
  criteria: Criterion[]
  eligibility?: {
    eligible: boolean
    probability: number
    threshold: number
    helped: { key: string; label: Bi; impact: number }[]
    held_back: { key: string; label: Bi; impact: number; tip: Bi }[]
    model: { name: string; version: string; trained_on: number; real_outcomes: number; simulated: boolean; auc: number; accuracy: number }
  } | null
  suggested_products: { type: string; reason: Bi; max_amount_tzs?: number; repayment_month?: string; status?: string }[]
  inputs: Record<string, any>
  disclaimer: Bi
  evidence?: {
    production: { harvests: { date: string; crop_type: string; quantity_kg: number; batch_id: string }[]; total_kg: number }
    storage: { receipts: { id: string; quantity_kg: number; grade: string; date_in: string; status: string }[]; windows: number; safe_windows: number; avg_humidity_pct: number | null }
    sales: { items: { id: string; date: string; quantity_kg: number; amount: number; buyer: string }[]; total_tzs: number; repeat_buyers: number }
    climate: { region: string; drought_prone: boolean; main_risk: string; crops: string[] }
  } | null
}

/** Eight months from now, marking the harvest month (income arrives after the sale). */
function nextMonths(harvest: string) {
  const now = new Date()
  const start = harvest < `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}` ? new Date(`${harvest}-01T00:00:00`) : new Date(now.getFullYear(), now.getMonth(), 1)
  return Array.from({ length: 8 }, (_, i) => {
    const d = new Date(start.getFullYear(), start.getMonth() + i, 1)
    const month = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
    return { month, harvest: month === harvest }
  })
}

const monthLabel = (ym: string, locale: string) => new Date(`${ym}-01T00:00:00`).toLocaleDateString(locale, { month: 'short', year: 'numeric' })

/** Explainable farmer profile. The level is always shown with the factors and the
 * verified records behind them, and with who decides (a person, not the model). */
export function ProfileView({ profile, audience = 'farmer', showCriteria = true }: { profile: Profile; audience?: 'farmer' | 'partner'; showCriteria?: boolean }) {
  const { t } = useTranslation()
  const bi = useBi()
  const f = useFormat()
  const ev = profile.evidence
  const flow = profile.cash_flow_estimate
  const safePct = ev?.storage.windows ? Math.round((ev.storage.safe_windows / ev.storage.windows) * 100) : null

  return (
    <div className="space-y-5">
      <Card>
        <div className="grid gap-5 md:grid-cols-[1fr_1.3fr] md:items-start">
          <div>
            <div className="eyebrow">{t('profile.riskLevel')}</div>
            <div className="mt-2 flex items-center gap-3">
              <span className="text-2xl font-semibold">{t(`risk.${profile.risk_band}`)}</span>
              <RiskBadge level={profile.risk_band} />
            </div>
            <div className="mt-3 max-w-[16rem]">
              <RiskScale level={profile.risk_band} />
            </div>
            <p className="mt-3 text-xs text-muted">
              {audience === 'partner' ? `${profile.display_name} · ${profile.farmer_id} · ${profile.region} · ` : ''}
              {t('profile.updated', { time: f.relative(profile.generated_at) })} · {profile.model_version}
            </p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <FactorList title={t('profile.positive')} items={profile.positive_factors.map((x) => bi(x))} kind="good" />
            <FactorList title={t('profile.risks')} items={profile.risk_factors.map((x) => bi(x))} kind="risk" />
          </div>
        </div>
        <Notice tone="neutral" className="mt-5">
          {bi(profile.disclaimer)} {audience === 'farmer' && t('profile.youControl')}
        </Notice>
      </Card>

      {showCriteria && <CreditCriteria criteria={profile.criteria} />}

      {ev && (
        <div className="grid gap-5 lg:grid-cols-2">
          <Card title={t('profile.production')} actions={<Wheat className="size-4 text-muted" aria-hidden />}>
            {ev.production.harvests.length ? (
              <>
                <p className="num text-sm text-muted">{t('profile.totalHarvested', { kg: f.kg(ev.production.total_kg), count: ev.production.harvests.length })}</p>
                <ul className="mt-3 divide-y divide-line text-sm">
                  {ev.production.harvests.map((h) => (
                    <li key={h.batch_id} className="flex items-center justify-between py-2">
                      <span>
                        {f.date(h.date)} · {t(`crops.${h.crop_type}`)}
                      </span>
                      <span className="num font-medium">{f.kg(h.quantity_kg)}</span>
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              <p className="text-sm text-muted">{t('profile.noProduction')}</p>
            )}
          </Card>

          <Card title={t('profile.storage')} actions={<Warehouse className="size-4 text-muted" aria-hidden />}>
            <KeyValues
              items={[
                [t('profile.receipts'), ev.storage.receipts.length],
                [t('profile.safeWindows'), safePct != null ? `${safePct}%` : '—'],
                [t('profile.avgHumidity'), ev.storage.avg_humidity_pct != null ? `${f.num(ev.storage.avg_humidity_pct, 1)}%` : '—'],
                [t('profile.unresolvedAlerts'), profile.inputs.unresolved_storage_alerts ?? 0],
              ]}
            />
          </Card>

          <Card title={t('profile.sales')} actions={<ShoppingBasket className="size-4 text-muted" aria-hidden />}>
            {ev.sales.items.length ? (
              <>
                <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
                  <span>
                    <span className="num font-semibold">{f.tzs(ev.sales.total_tzs)}</span> <span className="text-muted">{t('profile.verifiedTotal')}</span>
                  </span>
                  {ev.sales.repeat_buyers > 0 && <Badge tone="green">{t('profile.repeatBuyers', { count: ev.sales.repeat_buyers })}</Badge>}
                </div>
                <ul className="mt-3 divide-y divide-line text-sm">
                  {ev.sales.items.map((s) => (
                    <li key={s.id} className="flex items-center justify-between gap-3 py-2">
                      <span className="min-w-0 truncate">
                        {f.date(s.date)} · {s.buyer}
                      </span>
                      <span className="num shrink-0 font-medium">{f.tzs(s.amount)}</span>
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              <p className="text-sm text-muted">{t('profile.noSales')}</p>
            )}
          </Card>

          <Card title={t('profile.climate')} actions={<CloudSun className="size-4 text-muted" aria-hidden />}>
            <KeyValues
              items={[
                [t('auth.region'), ev.climate.region],
                [t('profile.mainRisk'), ev.climate.drought_prone ? <span className="text-warn-700">{t('profile.drought')}</span> : t('profile.noMajorRisk')],
                [t('profile.crops'), ev.climate.crops.map((c) => t(`crops.${c}`)).join(', ') || '—'],
                [t('profile.diversified'), ev.climate.crops.length > 1 ? t('common.yes') : t('common.no')],
              ]}
            />
          </Card>
        </div>
      )}

      <Card title={t('profile.cashFlow')} subtitle={t('profile.cashFlowSub')} actions={<Scale className="size-4 text-muted" aria-hidden />}>
        {flow.expected_income_range_tzs ? (
          <>
            <KeyValues
              cols={3}
              items={[
                [t('profile.nextHarvest'), flow.next_harvest_month ? monthLabel(flow.next_harvest_month, f.locale) : '—'],
                [t('profile.expectedYield'), f.kg(flow.expected_yield_kg)],
                [
                  t('profile.expectedIncome'),
                  <span className="num">
                    {f.tzs(flow.expected_income_range_tzs[0])} – {f.num(flow.expected_income_range_tzs[1])}
                  </span>,
                ],
              ]}
            />
            {flow.next_harvest_month && (
              <ol className="mt-4 grid grid-cols-8 gap-1.5" aria-label={t('profile.cashFlow')}>
                {nextMonths(flow.next_harvest_month).map((m) => (
                  <li key={m.month} className="text-center">
                    <div className="flex h-14 items-end rounded-sm bg-sunken">
                      <div className={cx('w-full rounded-sm', m.harvest ? 'h-full bg-harvest-500' : 'h-1 bg-line-strong')} />
                    </div>
                    <div className={cx('mt-1 truncate text-[11px]', m.harvest ? 'font-semibold text-ink' : 'text-muted')}>{monthLabel(m.month, f.locale).split(' ')[0]}</div>
                  </li>
                ))}
              </ol>
            )}
            <p className="mt-3 text-xs text-muted">
              {t('profile.priceBasis', { price: f.tzs(flow.price_per_kg_tzs), source: t(`profile.priceSource.${flow.price_source}`) })}
            </p>
          </>
        ) : (
          <p className="text-sm text-muted">{t('profile.noCashFlow')}</p>
        )}
      </Card>
    </div>
  )
}

function FactorList({ title, items, kind }: { title: string; items: string[]; kind: 'good' | 'risk' }) {
  const { t } = useTranslation()
  const Icon = kind === 'good' ? CheckCircle2 : AlertTriangle
  return (
    <div>
      <h3 className="text-sm font-semibold">{title}</h3>
      {items.length ? (
        <ul className="mt-2 space-y-2">
          {items.map((text, i) => (
            <li key={i} className="flex gap-2 text-[13px] text-ink-soft">
              <Icon className={cx('mt-px size-4 shrink-0', kind === 'good' ? 'text-forest-700' : 'text-warn-700')} aria-hidden />
              <span>{text}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-[13px] text-muted">{t('profile.none')}</p>
      )}
    </div>
  )
}

const CRITERION_ICON: Record<Criterion['key'], LucideIcon> = {
  transactions: Receipt,
  farm: Sprout,
  production: Wheat,
  offtake: FileSignature,
  condition: Gauge,
}
const LEVEL_STYLE = {
  good: { bar: 'bg-forest-700', tone: 'green' },
  fair: { bar: 'bg-harvest-500', tone: 'gold' },
  weak: { bar: 'bg-warn-700', tone: 'amber' },
} as const

/** The five criteria behind the credit assessment, each with its weight, score and the
 * findings that produced it. Tap a row to see the reasons. */
export function CreditCriteria({ criteria, open }: { criteria: Criterion[]; open?: boolean }) {
  const { t } = useTranslation()
  const bi = useBi()
  if (!criteria?.length) return null
  return (
    <Card title={t('credit.title')} subtitle={t('credit.subtitle')}>
      <ul className="-my-1 divide-y divide-line">
        {criteria.map((c) => {
          const Icon = CRITERION_ICON[c.key]
          const style = LEVEL_STYLE[c.level]
          return (
            <li key={c.key}>
              <details className="group py-3" open={open}>
                <summary className="flex cursor-pointer list-none items-center gap-3">
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-md bg-sunken text-ink-soft">
                    <Icon className="size-4" aria-hidden />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                      <span className="text-sm font-semibold">{bi(c.title)}</span>
                      <span className="text-xs text-muted">{t('credit.weight', { pct: c.weight })}</span>
                    </div>
                    <div className="mt-1.5 flex items-center gap-2">
                      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-line" role="img" aria-label={`${bi(c.title)}: ${c.score}/100`}>
                        <div className={cx('h-full rounded-full', style.bar)} style={{ width: `${c.score}%` }} />
                      </div>
                      <span className="num w-8 text-right text-xs font-semibold">{c.score}</span>
                    </div>
                  </div>
                  <Badge tone={style.tone}>{t(`credit.level.${c.level}`)}</Badge>
                  <ChevronRight className="size-4 shrink-0 text-muted transition-transform group-open:rotate-90" aria-hidden />
                </summary>
                <ul className="mt-3 space-y-1.5 pl-12">
                  {c.findings.map((finding, i) => (
                    <li key={i} className="flex gap-2 text-[13px] text-ink-soft">
                      {finding.good ? (
                        <CheckCircle2 className="mt-px size-4 shrink-0 text-forest-700" aria-hidden />
                      ) : (
                        <AlertTriangle className="mt-px size-4 shrink-0 text-warn-700" aria-hidden />
                      )}
                      <span>{bi(finding.text)}</span>
                    </li>
                  ))}
                </ul>
              </details>
            </li>
          )
        })}
      </ul>
    </Card>
  )
}
