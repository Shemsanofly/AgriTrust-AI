import { ArrowLeft, ChevronRight, CloudRain, FileText, Gauge, Scale, Umbrella, Users } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorNote,
  ErrorState,
  Field,
  KeyValues,
  Loading,
  Notice,
  PageHeader,
  Segmented,
  SimulatedTag,
  Stat,
  StatStrip,
  StatusBadge,
  useToast,
} from '../../components/ui'
import { api } from '../../lib/api'
import { useApi, useErrorText, useFormat } from '../../lib/hooks'
import { ProfileView, type Profile } from './ProfileView'
import { DocumentList, type LoanDoc } from './LoanDocuments'

type Loan = {
  id: number
  amount: number
  purpose: string
  status: string
  repayment_month: string | null
  decision_reason: string | null
  decided_by_name: string | null
  decided_at: string | null
  created_at: string
  farmer: { public_id: string; display_name: string; region: string }
  terms: { interest_rate_pct?: number; tenor_months?: number }
  consent: { state: string; expires_at: string } | null
  profile?: Profile | null
  documents: LoanDoc[]
}
type Consent = { id: number; state: string; data_categories: string[]; purpose: string; expires_at: string; granted_at: string; farmer: { public_id: string; display_name: string } }

const PENDING = ['SUBMITTED', 'UNDER_REVIEW']
const BOOK = ['APPROVED', 'DISBURSED', 'REPAYING', 'CLOSED']

function HumanDecides({ role }: { role: 'lender' | 'insurer' }) {
  const { t } = useTranslation()
  return <Notice tone="neutral">{t(`${role}.humanOnly`)}</Notice>
}

/* ================================================================== LENDER */

export function LenderOverview() {
  const { t } = useTranslation()
  const f = useFormat()
  const { data: loans, loading } = useApi<Loan[]>('/loans')
  const { data: consents } = useApi<Consent[]>('/consents')
  if (loading && !loans) return <Loading rows={3} />
  const pending = (loans ?? []).filter((l) => PENDING.includes(l.status))
  const book = (loans ?? []).filter((l) => BOOK.includes(l.status) && l.status !== 'CLOSED')
  const activeFarmers = new Set((consents ?? []).filter((c) => c.state === 'ACTIVE').map((c) => c.farmer.public_id))
  return (
    <div className="space-y-5">
      <PageHeader title={t('lender.overviewTitle')} subtitle={t('lender.overviewSubtitle')} actions={<SimulatedTag label={t('loans.simulatedLender')} />} />
      <StatStrip>
        <Stat icon={FileText} label={t('lender.toReview')} value={pending.length} sub={f.tzs(pending.reduce((s, l) => s + l.amount, 0))} tone={pending.length ? 'amber' : undefined} />
        <Stat icon={Scale} label={t('lender.activeBook')} value={f.tzs(book.reduce((s, l) => s + l.amount, 0))} sub={t('lender.loansCount', { count: book.length })} />
        <Stat icon={Users} label={t('lender.consentedFarmers')} value={activeFarmers.size} sub={t('lender.withActiveConsent')} />
        <Stat icon={Gauge} label={t('lender.decided')} value={(loans ?? []).filter((l) => l.decided_at).length} sub={t('lender.byPeople')} />
      </StatStrip>
      <HumanDecides role="lender" />
      <Card title={t('lender.queue')} padded={false} actions={<Link to="/applications" className="text-sm font-medium text-forest-800">{t('common.viewAll')}</Link>}>
        {!pending.length ? <EmptyState compact title={t('lender.queueEmpty')} /> : <LoanRows loans={pending} />}
      </Card>
    </div>
  )
}

function LoanRows({ loans }: { loans: Loan[] }) {
  const f = useFormat()
  return (
    <ul className="divide-y divide-line">
      {loans.map((l) => (
        <li key={l.id}>
          <Link to={`/applications/${l.id}`} className="flex items-center gap-3 px-4 py-3 hover:bg-sunken/60 sm:px-5">
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium">
                {l.farmer.display_name} <span className="font-normal text-muted">· {l.farmer.public_id} · {l.farmer.region}</span>
              </div>
              <div className="text-[13px] text-muted">
                <span className="num">{f.tzs(l.amount)}</span> · {l.purpose} · {f.relative(l.created_at)}
              </div>
            </div>
            <StatusBadge status={l.status} />
            <ChevronRight className="size-4 text-muted" aria-hidden />
          </Link>
        </li>
      ))}
    </ul>
  )
}

export function ApplicationsPage() {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const { data, loading, error, reload } = useApi<Loan[]>('/loans')
  const [filter, setFilter] = useState<'pending' | 'decided' | 'all'>('pending')
  const rows = (data ?? []).filter((l) => (filter === 'pending' ? PENDING.includes(l.status) : filter === 'decided' ? !PENDING.includes(l.status) : true))
  return (
    <div>
      <PageHeader title={t('nav.applications')} subtitle={t('lender.applicationsSubtitle')} />
      <Segmented
        label={t('common.filter')}
        value={filter}
        onChange={setFilter}
        options={[
          { id: 'pending', label: t('lender.pending') },
          { id: 'decided', label: t('lender.decidedTab') },
          { id: 'all', label: t('common.all') },
        ]}
      />
      <Card className="mt-4" padded={false}>
        {loading && !data ? (
          <div className="p-4">
            <Loading rows={2} />
          </div>
        ) : error ? (
          <ErrorState text={errorText(error)} onRetry={reload} />
        ) : !rows.length ? (
          <EmptyState icon={FileText} title={t('lender.noApplications')} />
        ) : (
          <LoanRows loans={rows} />
        )}
      </Card>
    </div>
  )
}

export function ApplicationDetail() {
  const { id } = useParams()
  const { t } = useTranslation()
  const f = useFormat()
  const toast = useToast()
  const errorText = useErrorText()
  const { data, loading, error, reload } = useApi<Loan>(`/loans/${id}`)
  const [form, setForm] = useState({ status: 'APPROVED', reason: '', rate: '18', tenor: '6' })
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  if (loading && !data) return <Loading rows={4} />
  if (error || !data) return <ErrorState text={errorText(error)} onRetry={reload} />

  const needsReason = ['APPROVED', 'DECLINED'].includes(form.status)
  const decide = async (e: FormEvent) => {
    e.preventDefault()
    if (needsReason && !form.reason.trim()) return setErr(t('errors.reason_required'))
    setBusy(true)
    setErr(null)
    try {
      await api(`/loans/${id}/decision`, { method: 'PATCH', body: { status: form.status, reason: form.reason.trim() || null, interest_rate_pct: Number(form.rate), tenor_months: Number(form.tenor) } })
      toast(t('lender.recorded'))
      reload()
    } catch (e2) {
      setErr(errorText(e2))
    } finally {
      setBusy(false)
    }
  }

  const options = PENDING.includes(data.status) ? ['UNDER_REVIEW', 'APPROVED', 'DECLINED'] : data.status === 'APPROVED' ? ['DISBURSED'] : data.status === 'DISBURSED' ? ['REPAYING'] : data.status === 'REPAYING' ? ['CLOSED'] : []

  return (
    <div className="space-y-5">
      <Link to="/applications" className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink">
        <ArrowLeft className="size-4" aria-hidden /> {t('nav.applications')}
      </Link>
      <PageHeader
        eyebrow={t('lender.applicationNo', { id: data.id })}
        title={`${data.farmer.display_name} · ${f.tzs(data.amount)}`}
        subtitle={`${data.purpose} · ${t('loans.repaymentMonth')}: ${data.repayment_month ?? '—'}`}
        actions={<StatusBadge status={data.status} />}
      />
      <div className="grid gap-5 lg:grid-cols-[1.6fr_1fr]">
        <div className="space-y-5">
          {data.profile ? <ProfileView profile={data.profile} audience="partner" /> : <Notice tone="warning" title={t('lender.noConsentTitle')}>{t('lender.noConsent')}</Notice>}
          {data.profile && <Notice tone="info">{t('lender.accessLogged')}</Notice>}
        </div>
        <div className="space-y-5">
          <Card title={t('loanDocs.title')} subtitle={t('loanDocs.lenderSub')}>
            {data.documents.length ? <DocumentList docs={data.documents} /> : <Notice tone="warning">{t('loanDocs.noneFromUssd')}</Notice>}
          </Card>
          <Card title={t('lender.decision')} subtitle={t('lender.decisionSub')}>
            {data.decision_reason && (
              <div className="mb-4 rounded-md bg-sunken p-3 text-[13px]">
                <div className="font-medium">{t('loans.humanDecision', { name: data.decided_by_name })}</div>
                <p className="mt-0.5 text-ink-soft">“{data.decision_reason}”</p>
                <p className="mt-1 text-xs text-muted">{f.dateTime(data.decided_at)}</p>
              </div>
            )}
            {options.length ? (
              <form onSubmit={decide} className="space-y-4">
                <Field label={t('lender.status')}>
                  <select className="input" value={options.includes(form.status) ? form.status : options[0]} onChange={(e) => setForm({ ...form, status: e.target.value })}>
                    {options.map((s) => (
                      <option key={s} value={s}>
                        {t(`status.${s}`)}
                      </option>
                    ))}
                  </select>
                </Field>
                {form.status === 'APPROVED' && options.includes('APPROVED') && (
                  <div className="grid grid-cols-2 gap-3">
                    <Field label={t('lender.rate')}>
                      <input className="input num" inputMode="decimal" value={form.rate} onChange={(e) => setForm({ ...form, rate: e.target.value })} />
                    </Field>
                    <Field label={t('lender.tenor')}>
                      <input className="input num" inputMode="numeric" value={form.tenor} onChange={(e) => setForm({ ...form, tenor: e.target.value })} />
                    </Field>
                  </div>
                )}
                <Field label={t('lender.reason')} hint={t('lender.reasonHint')}>
                  <textarea className="input min-h-20" value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} />
                </Field>
                <ErrorNote text={err} />
                <Button type="submit" busy={busy} className="w-full">
                  {t('lender.record')}
                </Button>
              </form>
            ) : (
              <p className="text-sm text-muted">{t('lender.noFurtherSteps')}</p>
            )}
          </Card>
          <Card title={t('lender.consentTitle')}>
            {data.consent ? (
              <KeyValues cols={1} items={[[t('lender.consentState'), <StatusBadge status={data.consent.state} />], [t('consent.untilLabel'), f.date(data.consent.expires_at)]]} />
            ) : (
              <p className="text-sm text-muted">—</p>
            )}
          </Card>
        </div>
      </div>
    </div>
  )
}

function useConsentedFarmers() {
  const q = useApi<Consent[]>('/consents')
  const farmers = new Map<string, { farmer: Consent['farmer']; consents: Consent[] }>()
  for (const c of q.data ?? []) {
    const row = farmers.get(c.farmer.public_id) ?? { farmer: c.farmer, consents: [] }
    row.consents.push(c)
    farmers.set(c.farmer.public_id, row)
  }
  return { ...q, farmers: [...farmers.values()] }
}

export function FarmersPage({ base = '/risk-profiles' }: { base?: string }) {
  const { t } = useTranslation()
  const f = useFormat()
  const errorText = useErrorText()
  const { farmers, data, loading, error, reload } = useConsentedFarmers()
  return (
    <div>
      <PageHeader title={t('nav.farmers')} subtitle={t('partners.farmersSubtitle')} />
      <Card padded={false}>
        {loading && !data ? (
          <div className="p-4">
            <Loading rows={2} />
          </div>
        ) : error ? (
          <ErrorState text={errorText(error)} onRetry={reload} />
        ) : !farmers.length ? (
          <EmptyState icon={Users} title={t('partners.noFarmers')} body={t('partners.noFarmersBody')} />
        ) : (
          <ul className="divide-y divide-line">
            {farmers.map(({ farmer, consents }) => {
              const active = consents.find((c) => c.state === 'ACTIVE')
              return (
                <li key={farmer.public_id}>
                  <Link to={active ? `${base}/${farmer.public_id}` : '#'} aria-disabled={!active} className="flex items-center gap-3 px-4 py-3 hover:bg-sunken/60 sm:px-5">
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-medium">
                        {farmer.display_name} <span className="font-normal text-muted">· {farmer.public_id}</span>
                      </div>
                      <div className="text-[13px] text-muted">
                        {active ? `${active.data_categories.map((c) => t(`consent.categories.${c}`)).join(', ')} · ${t('consent.until', { date: f.date(active.expires_at) })}` : t('partners.consentEnded')}
                      </div>
                    </div>
                    <StatusBadge status={active ? 'ACTIVE' : consents[0].state} />
                    {active && <ChevronRight className="size-4 text-muted" aria-hidden />}
                  </Link>
                </li>
              )
            })}
          </ul>
        )}
      </Card>
    </div>
  )
}

export function RiskProfilesPage() {
  return <FarmersPage base="/risk-profiles" />
}

export function RiskProfileDetail({ back = '/risk-profiles' }: { back?: string }) {
  const { farmerId } = useParams()
  const { t } = useTranslation()
  const errorText = useErrorText()
  const { data, loading, error, reload } = useApi<Profile>(`/farmers/${farmerId}/profile`)
  return (
    <div className="space-y-5">
      <Link to={back} className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink">
        <ArrowLeft className="size-4" aria-hidden /> {t('common.back')}
      </Link>
      {loading && !data ? (
        <Loading rows={4} />
      ) : error || !data ? (
        <ErrorState text={errorText(error)} onRetry={reload} />
      ) : (
        <>
          <PageHeader eyebrow={data.farmer_id} title={data.display_name} subtitle={data.region} />
          <Notice tone="info">{t('lender.accessLogged')}</Notice>
          <ProfileView profile={data} audience="partner" />
        </>
      )}
    </div>
  )
}

export function LoanBookPage() {
  const { t } = useTranslation()
  const f = useFormat()
  const { data, loading } = useApi<Loan[]>('/loans')
  const book = (data ?? []).filter((l) => BOOK.includes(l.status))
  return (
    <div>
      <PageHeader title={t('nav.loans')} subtitle={t('lender.bookSubtitle')} />
      <Card padded={false}>
        {loading && !data ? (
          <div className="p-4">
            <Loading rows={2} />
          </div>
        ) : !book.length ? (
          <EmptyState icon={Scale} title={t('lender.noBook')} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[40rem] text-left text-sm">
              <thead className="bg-sunken text-xs text-muted">
                <tr>
                  <th className="px-5 py-2.5 font-medium">{t('market.farmer')}</th>
                  <th className="px-3 py-2.5 text-right font-medium">{t('loans.principal')}</th>
                  <th className="px-3 py-2.5 text-right font-medium">{t('lender.terms')}</th>
                  <th className="px-3 py-2.5 text-right font-medium">{t('lender.dueAmount')}</th>
                  <th className="px-3 py-2.5 font-medium">{t('lender.dueMonth')}</th>
                  <th className="px-5 py-2.5 font-medium">{t('lender.status')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {book.map((l) => {
                  const rate = (l.terms.interest_rate_pct ?? 0) / 100
                  const months = l.terms.tenor_months ?? 6
                  const due = Math.round(l.amount * (1 + rate * (months / 12)))
                  return (
                    <tr key={l.id}>
                      <td className="px-5 py-3">
                        <Link to={`/applications/${l.id}`} className="font-medium hover:underline">
                          {l.farmer.display_name}
                        </Link>
                        <div className="text-xs text-muted">{l.purpose}</div>
                      </td>
                      <td className="num px-3 py-3 text-right">{f.tzs(l.amount)}</td>
                      <td className="num px-3 py-3 text-right text-muted">{l.terms.interest_rate_pct != null ? `${l.terms.interest_rate_pct}% · ${months}m` : '—'}</td>
                      <td className="num px-3 py-3 text-right">{f.tzs(due)}</td>
                      <td className="px-3 py-3">{l.repayment_month ?? '—'}</td>
                      <td className="px-5 py-3">
                        <StatusBadge status={l.status} />
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      <p className="mt-3 text-xs text-muted">{t('lender.bookNote')}</p>
    </div>
  )
}

/* ================================================================== INSURER */

type Policy = {
  id: number
  product: string
  coverage_tzs: number
  premium_tzs: number
  status: string
  rainfall_threshold_mm: number | null
  farmer: { public_id: string; display_name: string; region: string }
  claims: { id: number; trigger_type: string; status: string; decision_reason: string | null; evidence: Record<string, any>; created_at: string }[]
  created_at: string
}

export function InsurerOverview() {
  const { t } = useTranslation()
  const f = useFormat()
  const { data: policies, loading } = useApi<Policy[]>('/insurance/policies')
  if (loading && !policies) return <Loading rows={3} />
  const ps = policies ?? []
  const requested = ps.filter((p) => p.status === 'REQUESTED')
  const active = ps.filter((p) => p.status === 'ACTIVE')
  const claims = ps.flatMap((p) => p.claims.map((c) => ({ ...c, policy: p })))
  const openClaims = claims.filter((c) => !['APPROVED', 'REJECTED', 'PAID'].includes(c.status))
  return (
    <div className="space-y-5">
      <PageHeader title={t('insurer.overviewTitle')} subtitle={t('insurer.overviewSubtitle')} actions={<SimulatedTag label={t('insurance.simulatedInsurer')} />} />
      <StatStrip>
        <Stat icon={FileText} label={t('insurer.requests')} value={requested.length} tone={requested.length ? 'amber' : undefined} />
        <Stat icon={Umbrella} label={t('insurer.activePolicies')} value={active.length} sub={f.tzs(active.reduce((s, p) => s + p.coverage_tzs, 0))} />
        <Stat icon={CloudRain} label={t('insurer.openClaims')} value={openClaims.length} tone={openClaims.length ? 'amber' : undefined} />
        <Stat label={t('insurer.premiums')} value={f.tzs(active.reduce((s, p) => s + p.premium_tzs, 0))} />
      </StatStrip>
      <HumanDecides role="insurer" />
      <div className="grid gap-5 lg:grid-cols-2">
        <Card title={t('insurer.requests')} padded={false} actions={<Link to="/policies" className="text-sm font-medium text-forest-800">{t('common.viewAll')}</Link>}>
          {!requested.length ? <EmptyState compact title={t('insurer.noRequests')} /> : <PolicyRows policies={requested} />}
        </Card>
        <Card title={t('insurer.openClaims')} padded={false} actions={<Link to="/claims" className="text-sm font-medium text-forest-800">{t('common.viewAll')}</Link>}>
          {!openClaims.length ? (
            <EmptyState compact title={t('insurer.noClaims')} />
          ) : (
            <ul className="divide-y divide-line">
              {openClaims.map((c) => (
                <li key={c.id} className="flex items-center gap-3 px-4 py-3 text-sm sm:px-5">
                  <div className="min-w-0 flex-1">
                    <div className="font-medium">{c.policy.farmer.display_name}</div>
                    <div className="text-[13px] text-muted">{t(`insurance.triggerTypes.${c.trigger_type}`)} · {f.relative(c.created_at)}</div>
                  </div>
                  <StatusBadge status={c.status} />
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  )
}

function PolicyRows({ policies }: { policies: Policy[] }) {
  const { t } = useTranslation()
  const f = useFormat()
  return (
    <ul className="divide-y divide-line">
      {policies.map((p) => (
        <li key={p.id} className="flex items-center gap-3 px-4 py-3 text-sm sm:px-5">
          <div className="min-w-0 flex-1">
            <div className="font-medium">
              {p.farmer.display_name} <span className="font-normal text-muted">· {t(`products.${p.product}`)}</span>
            </div>
            <div className="num text-[13px] text-muted">
              {f.tzs(p.coverage_tzs)} · {t('insurance.premium')} {f.tzs(p.premium_tzs)}
            </div>
          </div>
          <StatusBadge status={p.status} />
        </li>
      ))}
    </ul>
  )
}

export function PoliciesPage() {
  const { t } = useTranslation()
  const f = useFormat()
  const toast = useToast()
  const errorText = useErrorText()
  const { data, loading, reload } = useApi<Policy[]>('/insurance/policies')
  const [error, setError] = useState<string | null>(null)
  const [results, setResults] = useState<Record<number, any>>({})

  const run = async (fn: () => Promise<unknown>, done?: string) => {
    setError(null)
    try {
      await fn()
      if (done) toast(done)
      reload()
    } catch (err) {
      setError(errorText(err))
    }
  }

  return (
    <div>
      <PageHeader title={t('nav.policies')} subtitle={t('insurer.policiesSubtitle')} />
      <ErrorNote text={error} />
      {loading && !data ? (
        <Loading />
      ) : !data?.length ? (
        <Card>
          <EmptyState icon={Umbrella} title={t('insurance.noPolicies')} />
        </Card>
      ) : (
        <div className="space-y-3">
          {data.map((p) => (
            <Card key={p.id} as="article">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <div className="font-semibold">
                    {p.farmer.display_name} <span className="font-normal text-muted">· {p.farmer.region}</span>
                  </div>
                  <div className="num text-[13px] text-muted">
                    {t(`products.${p.product}`)} · {f.tzs(p.coverage_tzs)} · {t('insurance.premium')} {f.tzs(p.premium_tzs)}
                    {p.rainfall_threshold_mm != null && ` · ${t('insurance.threshold', { mm: p.rainfall_threshold_mm })}`}
                  </div>
                </div>
                <StatusBadge status={p.status} />
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {p.status === 'REQUESTED' && (
                  <>
                    <Button size="sm" onClick={() => run(() => api(`/insurance/policies/${p.id}`, { method: 'PATCH', body: { status: 'ACTIVE' } }), t('insurer.activated'))}>
                      {t('insurer.activate')}
                    </Button>
                    <Button size="sm" variant="secondary" onClick={() => run(() => api(`/insurance/policies/${p.id}`, { method: 'PATCH', body: { status: 'DECLINED' } }))}>
                      {t('insurer.decline')}
                    </Button>
                  </>
                )}
                {p.status === 'ACTIVE' && p.product === 'weather_index' && (
                  <Button size="sm" variant="secondary" icon={CloudRain} onClick={() => run(async () => setResults({ ...results, [p.id]: await api(`/insurance/policies/${p.id}/check-trigger`, { method: 'POST' }) }))}>
                    {t('insurance.checkTrigger')}
                  </Button>
                )}
                <Link to={`/farm-risk/${p.farmer.public_id}`} className="inline-flex min-h-9 items-center px-2 text-[13px] font-medium text-forest-800">
                  {t('insurer.viewProfile')}
                </Link>
              </div>
              {results[p.id] && (
                <p className="mt-2 text-[13px]">
                  {t('insurance.rainfall', { mm: f.num(results[p.id].rainfall_mm, 1), threshold: results[p.id].threshold_mm })} {results[p.id].simulated && <SimulatedTag />} →{' '}
                  {results[p.id].triggered ? <Badge tone="amber">{t('insurance.triggered')}</Badge> : <Badge tone="green">{t('insurance.notTriggered')}</Badge>}
                </p>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}

export function FarmRiskPage() {
  return <FarmersPage base="/farm-risk" />
}

export function ClaimsPage() {
  const { t } = useTranslation()
  const f = useFormat()
  const toast = useToast()
  const errorText = useErrorText()
  const { data, loading, reload } = useApi<Policy[]>('/insurance/policies')
  const [reasons, setReasons] = useState<Record<number, string>>({})
  const [errors, setErrors] = useState<Record<number, string | null>>({})
  const claims = (data ?? []).flatMap((p) => p.claims.map((c) => ({ ...c, policy: p })))

  const decide = async (id: number, status: string) => {
    if (['APPROVED', 'REJECTED'].includes(status) && !reasons[id]?.trim()) return setErrors({ ...errors, [id]: t('errors.reason_required') })
    try {
      await api(`/insurance/claims/${id}/decision`, { method: 'PATCH', body: { status, reason: reasons[id]?.trim() || null } })
      setErrors({ ...errors, [id]: null })
      toast(t('insurer.claimRecorded'))
      reload()
    } catch (err) {
      setErrors({ ...errors, [id]: errorText(err) })
    }
  }

  return (
    <div>
      <PageHeader title={t('nav.claims')} subtitle={t('insurer.claimsSubtitle')} />
      {loading && !data ? (
        <Loading />
      ) : !claims.length ? (
        <Card>
          <EmptyState icon={Umbrella} title={t('insurer.noClaims')} />
        </Card>
      ) : (
        <div className="space-y-3">
          {claims.map((c) => {
            const decided = ['APPROVED', 'REJECTED', 'PAID'].includes(c.status)
            return (
              <Card key={c.id} as="article">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <div className="font-semibold">
                      {t('insurance.claimX', { id: c.id })} · {c.policy.farmer.display_name}
                    </div>
                    <div className="text-[13px] text-muted">
                      {t(`insurance.triggerTypes.${c.trigger_type}`)} · {t(`products.${c.policy.product}`)} · {f.date(c.created_at)}
                    </div>
                  </div>
                  <StatusBadge status={c.status} />
                </div>
                <div className="mt-3 rounded-md bg-sunken p-3 text-[13px]">
                  <div className="mb-1 font-medium">{t('insurer.evidence')}</div>
                  {c.evidence.rainfall_mm != null ? (
                    <p>
                      {t('insurance.rainfall', { mm: f.num(c.evidence.rainfall_mm, 1), threshold: c.evidence.threshold_mm })} ({c.evidence.window_start} → {c.evidence.window_end}) {c.evidence.simulated && <SimulatedTag />}
                    </p>
                  ) : (
                    <p>“{c.evidence.description}”</p>
                  )}
                </div>
                {c.decision_reason && <p className="mt-2 text-[13px]">“{c.decision_reason}”</p>}
                {!decided && (
                  <div className="mt-3 space-y-2">
                    <textarea className="input min-h-16" placeholder={t('lender.reason')} aria-label={t('lender.reason')} value={reasons[c.id] ?? ''} onChange={(e) => setReasons({ ...reasons, [c.id]: e.target.value })} />
                    <ErrorNote text={errors[c.id]} />
                    <div className="flex flex-wrap gap-2">
                      <Button size="sm" onClick={() => decide(c.id, 'APPROVED')}>
                        {t('insurer.approve')}
                      </Button>
                      <Button size="sm" variant="danger" onClick={() => decide(c.id, 'REJECTED')}>
                        {t('insurer.reject')}
                      </Button>
                      {c.status !== 'UNDER_REVIEW' && (
                        <Button size="sm" variant="secondary" onClick={() => decide(c.id, 'UNDER_REVIEW')}>
                          {t('insurer.review')}
                        </Button>
                      )}
                    </div>
                  </div>
                )}
                {c.status === 'APPROVED' && (
                  <Button size="sm" variant="secondary" className="mt-3" onClick={() => decide(c.id, 'PAID')}>
                    {t('insurer.markPaid')}
                  </Button>
                )}
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}

