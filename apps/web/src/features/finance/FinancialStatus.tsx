import { AlertTriangle, CheckCircle2, ChevronRight, HandCoins, PiggyBank, ShieldCheck, TrendingUp, Umbrella, type LucideIcon } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button, Card, cx } from '../../components/ui'
import { useApi, useFormat } from '../../lib/hooks'
import { ContestProfile } from './FinanceTabs'
import { CreditCriteria, ProfileView, type Profile } from './ProfileView'

type Loan = { amount: number; status: string }
type Goal = { saved_amount: number }
type Policy = { coverage_tzs: number; status: string }

const ACTIVE_LOAN = ['APPROVED', 'DISBURSED', 'REPAYING']
const PENDING_LOAN = ['SUBMITTED', 'UNDER_REVIEW']

/** Plain-language health for each risk band. */
const HEALTH = {
  LOW: {
    key: 'good',
    box: 'bg-forest-50',
    text: 'text-forest-800',
    icon: CheckCircle2,
  },
  MEDIUM: {
    key: 'fair',
    box: 'bg-harvest-100',
    text: 'text-harvest-800',
    icon: TrendingUp,
  },
  HIGH: {
    key: 'weak',
    box: 'bg-warn-100',
    text: 'text-warn-700',
    icon: AlertTriangle,
  },
} as const

export type FinanceTab = 'loans' | 'savings' | 'insurance' | 'sharing'

/** One-screen summary of the farmer's money: health, earnings, loans, savings and insurance. */
export function FinancialStatus({ profile, onOpen }: { profile: Profile; onOpen: (tab: FinanceTab) => void }) {
  const { t } = useTranslation()
  const f = useFormat()
  const { data: loans } = useApi<Loan[]>('/loans')
  const { data: goals } = useApi<Goal[]>('/savings/goals')
  const { data: policies } = useApi<Policy[]>('/insurance/policies')

  const health = HEALTH[profile.risk_band]
  const flow = profile.cash_flow_estimate
  const earned = profile.evidence?.sales.total_tzs ?? 0
  const loanOffer = profile.suggested_products.find((p) => p.type === 'input_loan')

  const activeLoans = (loans ?? []).filter((l) => ACTIVE_LOAN.includes(l.status))
  const pendingLoans = (loans ?? []).filter((l) => PENDING_LOAN.includes(l.status)).length
  const owed = activeLoans.reduce((s, l) => s + l.amount, 0)
  const saved = (goals ?? []).reduce((s, g) => s + g.saved_amount, 0)
  const covered = (policies ?? []).filter((p) => p.status === 'ACTIVE')
  const requested = (policies ?? []).filter((p) => p.status === 'REQUESTED').length

  return (
    <div className="space-y-5">
      <Card>
        <div className="flex items-start gap-3">
          <span className={cx('flex size-12 shrink-0 items-center justify-center rounded-md', health.box, health.text)}>
            <health.icon className="size-6" aria-hidden />
          </span>
          <div>
            <div className="eyebrow">{t('finance.status.health')}</div>
            <div className={cx('text-2xl font-semibold', health.text)}>{t(`finance.status.band.${health.key}`)}</div>
            <p className="mt-0.5 max-w-md text-sm text-muted">{t(`finance.status.meaning.${health.key}`)}</p>
          </div>
        </div>
        {flow.expected_income_range_tzs && (
          <p className="num mt-4 rounded-md bg-sunken px-3 py-2 text-sm">
            {t('finance.status.nextIncome', {
              low: f.tzs(flow.expected_income_range_tzs[0]),
              high: f.num(flow.expected_income_range_tzs[1]),
              month: flow.next_harvest_month ? f.month(flow.next_harvest_month) : '—',
            })}
          </p>
        )}
      </Card>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Tile
          icon={TrendingUp}
          label={t('finance.status.earned')}
          value={f.tzs(earned)}
          sub={t('finance.status.earnedSub', {
            count: profile.evidence?.sales.items.length ?? 0,
          })}
        />
        <Tile
          icon={HandCoins}
          label={t('finance.tabs.loans')}
          value={owed > 0 ? f.tzs(owed) : t('finance.status.noLoan')}
          sub={
            owed > 0
              ? t('finance.status.loanActive', { count: activeLoans.length })
              : pendingLoans
                ? t('finance.status.loanPending', { count: pendingLoans })
                : loanOffer?.max_amount_tzs
                  ? t('finance.status.loanOffer', {
                      amount: f.tzs(loanOffer.max_amount_tzs),
                    })
                  : profile.eligibility && !profile.eligibility.eligible
                    ? t('finance.status.loanNotYet', { pct: Math.round(profile.eligibility.probability * 100) })
                    : undefined
          }
          action={t('finance.status.openLoans')}
          onClick={() => onOpen('loans')}
        />
        <Tile
          icon={PiggyBank}
          label={t('finance.tabs.savings')}
          value={f.tzs(saved)}
          sub={t('finance.status.goals', { count: goals?.length ?? 0 })}
          action={t('finance.status.openSavings')}
          onClick={() => onOpen('savings')}
        />
        <Tile
          icon={Umbrella}
          label={t('finance.tabs.insurance')}
          value={covered.length ? f.tzs(covered.reduce((s, p) => s + p.coverage_tzs, 0)) : t('finance.status.notCovered')}
          sub={covered.length ? t('finance.status.policies', { count: covered.length }) : requested ? t('finance.status.policyRequested', { count: requested }) : t('finance.status.getCover')}
          tone={covered.length ? undefined : 'amber'}
          action={t('finance.status.openInsurance')}
          onClick={() => onOpen('insurance')}
        />
      </div>

      <CreditCriteria criteria={profile.criteria} />

      <details className="group rounded-(--radius-card) border border-line bg-surface">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-4 py-3.5 text-sm font-medium sm:px-5">
          {t('finance.status.fullRecord')}
          <ChevronRight className="size-4 text-muted transition-transform group-open:rotate-90" aria-hidden />
        </summary>
        <div className="space-y-5 border-t border-line p-4 sm:p-5">
          <ProfileView profile={profile} showCriteria={false} />
          <ContestProfile />
        </div>
      </details>

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-(--radius-card) border border-line bg-surface px-4 py-3 sm:px-5">
        <div className="flex items-center gap-3 text-sm">
          <ShieldCheck className="size-5 shrink-0 text-forest-700" aria-hidden />
          <span>{t('finance.status.sharing')}</span>
        </div>
        <Button size="sm" variant="secondary" onClick={() => onOpen('sharing')}>
          {t('finance.status.manage')}
        </Button>
      </div>
    </div>
  )
}

function Tile({ icon: Icon, label, value, sub, tone, action, onClick }: { icon: LucideIcon; label: string; value: string; sub?: string; tone?: 'amber'; action?: string; onClick?: () => void }) {
  const body = (
    <>
      <div className="flex items-center gap-2 text-[13px] text-muted">
        <Icon className="size-4 shrink-0" aria-hidden />
        {label}
      </div>
      <div className={cx('num mt-1.5 text-lg font-semibold tracking-tight sm:text-xl', tone === 'amber' ? 'text-warn-700' : 'text-ink')}>{value}</div>
      {sub && <div className="mt-0.5 text-xs text-muted">{sub}</div>}
      {action && (
        <div className="mt-auto flex items-center gap-1 pt-3 text-[13px] font-medium text-forest-800">
          {action} <ChevronRight className="size-3.5" aria-hidden />
        </div>
      )}
    </>
  )
  const box = 'flex flex-col items-start rounded-(--radius-card) border border-line bg-surface p-3.5 text-left sm:p-4'
  return onClick ? (
    <button type="button" onClick={onClick} className={cx(box, 'transition-colors hover:border-forest-700 hover:bg-forest-50/40')}>
      {body}
    </button>
  ) : (
    <div className={box}>{body}</div>
  )
}
