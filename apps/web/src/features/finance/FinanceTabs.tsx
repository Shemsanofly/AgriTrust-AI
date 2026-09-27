import { BrainCircuit, CheckCircle2, CircleDashed, CloudRain, FileText, HandCoins, Lightbulb, TrendingDown, TrendingUp, Umbrella, Warehouse } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { ConfirmAction } from '../../components/ConfirmAction'
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorNote,
  Field,
  KeyValues,
  Notice,
  ProgressBar,
  RiskBadge,
  SimulatedTag,
  Skeleton,
  StatusBadge,
  cx,
  useToast,
} from '../../components/ui'
import { api } from '../../lib/api'
import { useApi, useBi, useErrorText, useFormat, type Bi } from '../../lib/hooks'
import type { Batch } from '../farmer/shared'
import { HazardForecast } from './HazardForecast'
import { DocumentList, DocumentPicker, type LoanDoc } from './LoanDocuments'
import type { Profile } from './ProfileView'

export function ContestProfile() {
  const { t } = useTranslation()
  const toast = useToast()
  const errorText = useErrorText()
  const [text, setText] = useState('')
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (text.trim().length < 5) return setError(t('validation.describe'))
    try {
      await api('/farmers/me/profile/contest', { method: 'POST', body: { description: text.trim() } })
      toast(t('profile.contestSent'))
      setText('')
      setOpen(false)
    } catch (err) {
      setError(errorText(err))
    }
  }
  return (
    <Card title={t('profile.contestTitle')} subtitle={t('profile.contestSub')} actions={!open && <Button variant="secondary" size="sm" onClick={() => setOpen(true)}>{t('profile.contestOpen')}</Button>}>
      {open ? (
        <form onSubmit={submit} className="space-y-3">
          <textarea className="input min-h-24" value={text} onChange={(e) => setText(e.target.value)} placeholder={t('profile.contestPlaceholder')} aria-label={t('profile.contestTitle')} />
          <ErrorNote text={error} />
          <div className="flex gap-2">
            <Button type="submit">{t('profile.contestSend')}</Button>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              {t('common.cancel')}
            </Button>
          </div>
        </form>
      ) : (
        <p className="text-[13px] text-muted">{t('profile.contestBody')}</p>
      )}
    </Card>
  )
}

/* ------------------------------------------------------------------ loans */

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
  lender: { id: number; name: string }
  terms: { interest_rate_pct?: number; tenor_months?: number }
  documents: LoanDoc[]
}

const LOAN_STEPS = ['SUBMITTED', 'UNDER_REVIEW', 'APPROVED', 'DISBURSED', 'REPAYING', 'CLOSED']

/** Estimated repayment: one payment after the harvest sale (seasonal loan). */
function schedule(loan: Loan) {
  const rate = (loan.terms.interest_rate_pct ?? 0) / 100
  const months = loan.terms.tenor_months ?? 6
  const interest = Math.round(loan.amount * rate * (months / 12))
  return { interest, total: loan.amount + interest, due: loan.repayment_month }
}

export function LoansTab({ profile }: { profile: Profile | null }) {
  const { t } = useTranslation()
  const bi = useBi()
  const f = useFormat()
  const toast = useToast()
  const { data: loans, reload } = useApi<Loan[]>('/loans')
  const { data: lenders } = useApi<{ id: number; name: string }[]>('/partners?role=LENDER')
  const suggestion = profile?.suggested_products.find((p) => p.type === 'input_loan')
  const [form, setForm] = useState({ lender: '', amount: '', purpose: '', month: '' })
  const [docs, setDocs] = useState<LoanDoc[]>([])
  const [confirm, setConfirm] = useState(false)
  const [touched, setTouched] = useState(false)
  const amount = Number(form.amount.replace(/[, ]/g, ''))
  const lender = lenders?.find((l) => String(l.id) === form.lender) ?? lenders?.[0]
  const month = form.month || suggestion?.repayment_month || ''
  const problems = {
    amount: !(amount > 0) ? t('validation.amount') : null,
    purpose: form.purpose.trim().length < 3 ? t('validation.purpose') : null,
    document: docs.length ? null : t('loanDocs.required'),
  }
  const overMax = suggestion?.max_amount_tzs != null && amount > suggestion.max_amount_tzs

  const elig = profile?.eligibility

  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_1.1fr]">
      <div className="space-y-5">
        <Card title={t('loans.productTitle')} subtitle={t('loans.productSub')} actions={<SimulatedTag label={t('loans.simulatedLender')} />}>
          {suggestion ? (
            <>
              <div className="flex items-center gap-3">
                <span className="flex size-10 items-center justify-center rounded-md bg-harvest-100 text-harvest-800">
                  <HandCoins className="size-5" aria-hidden />
                </span>
                <div>
                  <div className="font-semibold">{t('products.input_loan')}</div>
                  <div className="text-[13px] text-muted">{bi(suggestion.reason)}</div>
                </div>
              </div>
              <KeyValues
                items={[
                  [t('loans.upTo'), <span className="num">{f.tzs(suggestion.max_amount_tzs)}</span>],
                  [t('loans.repayAfter'), suggestion.repayment_month ? f.month(suggestion.repayment_month) : '—'],
                ]}
              />
            </>
          ) : (
            <p className="text-sm text-muted">{t('loans.noProduct')}</p>
          )}
          {elig && <AiVerdict elig={elig} />}
          {!elig && <p className="mt-3 text-xs text-muted">{t('loans.eligibilityNote')}</p>}
        </Card>

        <Card title={t('loans.applyTitle')}>
          <form
            onSubmit={(e) => {
              e.preventDefault()
              setTouched(true)
              if (!Object.values(problems).some(Boolean)) setConfirm(true)
            }}
            className="space-y-4"
            noValidate
          >
            <Field label={t('loans.lender')}>
              <select className="input" value={form.lender} onChange={(e) => setForm({ ...form, lender: e.target.value })}>
                {lenders?.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.name}
                  </option>
                ))}
              </select>
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label={t('loans.amount')} error={touched ? problems.amount : null} hint={overMax ? t('loans.overSuggested') : undefined}>
                <input className="input num" inputMode="numeric" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} placeholder={suggestion?.max_amount_tzs ? String(suggestion.max_amount_tzs) : ''} />
              </Field>
              <Field label={t('loans.repaymentMonth')}>
                <input className="input" type="month" value={month} onChange={(e) => setForm({ ...form, month: e.target.value })} />
              </Field>
            </div>
            <Field label={t('loans.purpose')} error={touched ? problems.purpose : null}>
              <input className="input" value={form.purpose} onChange={(e) => setForm({ ...form, purpose: e.target.value })} placeholder={t('loans.purposePlaceholder')} />
            </Field>
            <DocumentPicker docs={docs} onChange={setDocs} error={touched ? problems.document : null} />
            <Notice tone="neutral">{t('loans.consentNote')}</Notice>
            <Button type="submit">{t('loans.review')}</Button>
          </form>
        </Card>
      </div>

      <Card title={t('loans.myApplications')}>
        {!loans ? (
          <Skeleton className="h-24" />
        ) : !loans.length ? (
          <EmptyState compact icon={FileText} title={t('loans.none')} body={t('loans.noneBody')} />
        ) : (
          <ul className="-my-3 divide-y divide-line">
            {loans.map((l) => {
              const step = LOAN_STEPS.indexOf(l.status)
              const s = schedule(l)
              return (
                <li key={l.id} className="py-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="font-semibold">
                      <span className="num">{f.tzs(l.amount)}</span> <span className="font-normal text-muted">· {l.purpose}</span>
                    </div>
                    <StatusBadge status={l.status} />
                  </div>
                  <p className="text-xs text-muted">
                    {l.lender.name} · {t('loans.appliedOn', { date: f.date(l.created_at) })}
                  </p>
                  {l.status !== 'DECLINED' && (
                    <ol className="mt-3 flex gap-1">
                      {LOAN_STEPS.map((st, i) => (
                        <li key={st} className="min-w-0 flex-1">
                          <div className={cx('h-1 rounded-full', i <= step ? 'bg-forest-700' : 'bg-line')} />
                        </li>
                      ))}
                    </ol>
                  )}
                  {l.documents?.length > 0 && (
                    <div className="mt-3">
                      <DocumentList docs={l.documents} />
                    </div>
                  )}
                  {l.decision_reason && (
                    <p className="mt-3 rounded-md bg-sunken px-3 py-2 text-[13px]">
                      <span className="font-medium">{t('loans.humanDecision', { name: l.decided_by_name })}:</span> {l.decision_reason}
                    </p>
                  )}
                  {['APPROVED', 'DISBURSED', 'REPAYING'].includes(l.status) && l.terms.interest_rate_pct != null && (
                    <div className="mt-3 rounded-md border border-line p-3 text-[13px]">
                      <div className="mb-2 flex items-center justify-between font-semibold">
                        {t('loans.schedule')} <Badge>{t('common.estimate')}</Badge>
                      </div>
                      <table className="num w-full">
                        <tbody className="divide-y divide-line">
                          <tr>
                            <td className="py-1.5 text-muted">{t('loans.principal')}</td>
                            <td className="text-right whitespace-nowrap">{f.tzs(l.amount)}</td>
                          </tr>
                          <tr>
                            <td className="py-1.5 text-muted">{t('loans.interest', { rate: l.terms.interest_rate_pct, months: l.terms.tenor_months })}</td>
                            <td className="text-right whitespace-nowrap">{f.tzs(s.interest)}</td>
                          </tr>
                          <tr className="font-semibold">
                            <td className="py-1.5">{t('loans.dueAfterHarvest', { month: s.due ? f.month(s.due) : '—' })}</td>
                            <td className="text-right whitespace-nowrap">{f.tzs(s.total)}</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </Card>

      <ConfirmAction
        open={confirm}
        title={t('loans.confirmTitle')}
        summary={[
          [t('loans.lender'), lender?.name],
          [t('loans.amount'), f.tzs(amount)],
          [t('loans.purpose'), form.purpose],
          [t('loans.repaymentMonth'), month ? f.month(month) : '—'],
          [t('loanDocs.title'), docs.map((d) => t(`loanDocs.types.${d.doc_type}`)).join(', ')],
          [t('loans.sharedData'), t('loans.sharedDataValue')],
        ]}
        note={t('loans.decisionNote')}
        confirmLabel={t('loans.submit')}
        onClose={() => setConfirm(false)}
        onConfirm={async (pin) => {
          await api('/loans', { method: 'POST', body: { lender_user_id: lender?.id, amount, purpose: form.purpose.trim(), repayment_month: month || null, confirm_pin: pin, document_ids: docs.map((d) => d.id) } })
          setForm({ lender: '', amount: '', purpose: '', month: '' })
          setDocs([])
          setTouched(false)
          toast(t('loans.submitted'))
          reload()
        }}
      />
    </div>
  )
}

/* ------------------------------------------------------------------ insurance */

type Policy = {
  id: number
  product: string
  coverage_tzs: number
  premium_tzs: number
  status: string
  rainfall_threshold_mm: number | null
  window_start: string | null
  window_end: string | null
  insurer: { id: number; name: string }
  claims: { id: number; trigger_type: string; status: string; decision_reason: string | null; evidence: Record<string, any>; created_at: string }[]
}
type Rec = { product: string; farm_id?: number; suggested_coverage_tzs: number; indicative_premium_tzs: number; rainfall_threshold_mm?: number; reason: Bi; priority: string }

export function InsuranceTab({ profile }: { profile: Profile | null }) {
  const { t } = useTranslation()
  const bi = useBi()
  const f = useFormat()
  const toast = useToast()
  const errorText = useErrorText()
  const { data: recs } = useApi<{ recommendations: Rec[] }>('/insurance/recommendations')
  const { data: policies, reload } = useApi<Policy[]>('/insurance/policies')
  const { data: insurers } = useApi<{ id: number; name: string }[]>('/partners?role=INSURER')
  const { data: batches } = useApi<Batch[]>('/batches')
  const [requesting, setRequesting] = useState<Rec | null>(null)
  const [trigger, setTrigger] = useState<Record<number, any>>({})
  const [busy, setBusy] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const insurer = insurers?.[0]
  const stored = (batches ?? []).filter((b) => b.status === 'IN_STORAGE')
  const worstStorage = ['HIGH', 'MEDIUM', 'LOW'].find((lvl) => stored.some((b) => b.risk?.level === lvl))
  const has = (product: string) => policies?.some((p) => p.product === product && ['REQUESTED', 'ACTIVE'].includes(p.status))

  const check = async (id: number) => {
    setBusy(id)
    setError(null)
    try {
      setTrigger({ ...trigger, [id]: await api(`/insurance/policies/${id}/check-trigger`, { method: 'POST' }) })
      reload()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="space-y-5">
      <HazardForecast onInsurance={() => document.getElementById('insurance-recs')?.scrollIntoView({ behavior: 'smooth', block: 'start' })} />
      <div className="grid gap-5 lg:grid-cols-2">
        <Card title={t('insurance.riskTitle')} subtitle={t('insurance.riskSub')}>
          <ul className="space-y-3 text-sm">
            <li className="flex items-start gap-3">
              <CloudRain className="mt-0.5 size-5 shrink-0 text-info-700" aria-hidden />
              <div>
                <div className="font-medium">{t('insurance.climateRisk')}</div>
                <div className="text-[13px] text-muted">{profile?.evidence?.climate.drought_prone ? t('insurance.droughtProne', { region: profile.evidence.climate.region }) : t('insurance.noDrought')}</div>
              </div>
            </li>
            <li className="flex items-start gap-3">
              <Warehouse className="mt-0.5 size-5 shrink-0 text-earth-700" aria-hidden />
              <div className="flex-1">
                <div className="flex items-center gap-2 font-medium">
                  {t('insurance.storageRisk')} {worstStorage && <RiskBadge level={worstStorage} />}
                </div>
                <div className="text-[13px] text-muted">{stored.length ? t('insurance.storedKg', { kg: f.kg(stored.reduce((s, b) => s + b.available_kg, 0)) }) : t('ghala.nothingStored')}</div>
              </div>
            </li>
          </ul>
        </Card>
        <div id="insurance-recs" className="scroll-mt-4">
        <Card title={t('insurance.recommendations')} actions={<SimulatedTag label={t('insurance.simulatedInsurer')} />}>
          {!recs ? (
            <Skeleton className="h-24" />
          ) : !recs.recommendations.length ? (
            <EmptyState compact title={t('insurance.noRecs')} />
          ) : (
            <ul className="-my-2 divide-y divide-line">
              {recs.recommendations.map((r) => (
                <li key={`${r.product}-${r.farm_id ?? 0}`} className="py-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold">{t(`products.${r.product}`)}</span>
                    {r.priority === 'HIGH' && <Badge tone="gold">{t('insurance.recommended')}</Badge>}
                  </div>
                  <p className="mt-0.5 text-[13px] text-muted">{bi(r.reason)}</p>
                  <p className="num mt-1.5 text-[13px]">
                    {t('insurance.coverage')} <b>{f.tzs(r.suggested_coverage_tzs)}</b> · {t('insurance.premium')} ~<b>{f.tzs(r.indicative_premium_tzs)}</b>
                  </p>
                  <Button size="sm" className="mt-2" variant={has(r.product) ? 'secondary' : 'primary'} disabled={has(r.product)} onClick={() => setRequesting(r)}>
                    {has(r.product) ? t('insurance.alreadyRequested') : t('insurance.request')}
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </Card>
        </div>
      </div>

      <Card title={t('insurance.myPolicies')}>
        <ErrorNote text={error} />
        {!policies ? (
          <Skeleton className="h-24" />
        ) : !policies.length ? (
          <EmptyState compact icon={Umbrella} title={t('insurance.noPolicies')} body={t('insurance.noPoliciesBody')} />
        ) : (
          <ul className="-my-3 divide-y divide-line">
            {policies.map((p) => {
              const tr = trigger[p.id] ?? p.claims.find((c) => c.trigger_type === 'PARAMETRIC_RAINFALL')?.evidence
              return (
                <li key={p.id} className="py-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-semibold">{t(`products.${p.product}`)}</span>
                    <StatusBadge status={p.status} />
                  </div>
                  <p className="num text-[13px] text-muted">
                    {p.insurer.name} · {t('insurance.coverage')} {f.tzs(p.coverage_tzs)} · {t('insurance.premium')} {f.tzs(p.premium_tzs)}
                  </p>
                  {p.product === 'weather_index' && p.rainfall_threshold_mm != null && (
                    <div className="mt-3 rounded-md border border-line p-3">
                      <div className="flex flex-wrap items-center justify-between gap-2 text-[13px]">
                        <span className="font-medium">{t('insurance.parametric')}</span>
                        {tr?.rainfall_mm != null && (tr.triggered ? <Badge tone="amber">{t('insurance.triggered')}</Badge> : <Badge tone="green">{t('insurance.notTriggered')}</Badge>)}
                      </div>
                      {tr?.rainfall_mm != null ? (
                        <>
                          <div className="mt-2">
                            <ProgressBar value={tr.rainfall_mm} max={p.rainfall_threshold_mm} tone={tr.triggered ? 'gold' : 'green'} label={t('insurance.rainfall', { mm: tr.rainfall_mm, threshold: p.rainfall_threshold_mm })} />
                          </div>
                          <p className="num mt-1.5 text-xs text-muted">
                            {t('insurance.rainfall', { mm: f.num(tr.rainfall_mm, 1), threshold: p.rainfall_threshold_mm })} {tr.simulated && <SimulatedTag />}
                          </p>
                        </>
                      ) : (
                        <p className="mt-1 text-xs text-muted">{t('insurance.threshold', { mm: p.rainfall_threshold_mm })}</p>
                      )}
                      {p.status === 'ACTIVE' && (
                        <Button size="sm" variant="secondary" icon={CloudRain} className="mt-2" busy={busy === p.id} onClick={() => check(p.id)}>
                          {t('insurance.checkTrigger')}
                        </Button>
                      )}
                    </div>
                  )}
                  {p.claims.map((c) => (
                    <div key={c.id} className="mt-2 flex flex-wrap items-center gap-2 text-[13px]">
                      <Umbrella className="size-4 text-muted" aria-hidden />
                      {t('insurance.claimX', { id: c.id })} · {t(`insurance.triggerTypes.${c.trigger_type}`)} <StatusBadge status={c.status} />
                      {c.decision_reason && <span className="w-full pl-6 text-muted">“{c.decision_reason}”</span>}
                    </div>
                  ))}
                </li>
              )
            })}
          </ul>
        )}
        <p className="mt-3 text-xs text-muted">{t('insurance.humanNote')}</p>
      </Card>

      <ConfirmAction
        open={requesting != null}
        title={t('insurance.confirmTitle')}
        summary={
          requesting
            ? [
                [t('insurance.product'), t(`products.${requesting.product}`)],
                [t('insurance.insurer'), insurer?.name],
                [t('insurance.coverage'), f.tzs(requesting.suggested_coverage_tzs)],
                [t('insurance.premium'), f.tzs(requesting.indicative_premium_tzs)],
              ]
            : []
        }
        note={t('insurance.consentNote')}
        confirmLabel={t('insurance.request')}
        onClose={() => setRequesting(null)}
        onConfirm={async (pin) => {
          await api('/insurance/policies', {
            method: 'POST',
            body: { insurer_user_id: insurer?.id, product: requesting!.product, coverage_tzs: requesting!.suggested_coverage_tzs, farm_id: requesting!.farm_id ?? null, confirm_pin: pin },
          })
          toast(t('insurance.requested'))
          reload()
        }}
      />
    </div>
  )
}

/** The AI model's loan verdict: probability of repaying, and the farmer's own activities that
 * pushed it up or down (the model's per-feature contributions), with a tip for each weakness. */
function AiVerdict({ elig }: { elig: NonNullable<Profile['eligibility']> }) {
  const { t } = useTranslation()
  const bi = useBi()
  const pct = Math.round(elig.probability * 100)
  return (
    <div className="mt-5 space-y-4">
      <div className={cx('rounded-md px-3 py-3', elig.eligible ? 'bg-forest-50 text-forest-900' : 'bg-warn-100 text-warn-700')}>
        <div className="flex items-start gap-3">
          <BrainCircuit className="mt-0.5 size-5 shrink-0" aria-hidden />
          <div className="min-w-0 flex-1">
            <div className="text-[13px] font-medium">{t('ai.prediction')}</div>
            <div className="text-lg font-semibold">{t('ai.likely', { pct })}</div>
            <div className="text-sm">{elig.eligible ? t('ai.eligibleYes') : t('ai.eligibleNo')}</div>
          </div>
        </div>
        <div className="relative mt-3 h-2 rounded-full bg-white/70" role="img" aria-label={t('ai.likely', { pct })}>
          <div className={cx('h-full rounded-full', elig.eligible ? 'bg-forest-700' : 'bg-warn-700')} style={{ width: `${pct}%` }} />
          <div className="absolute -top-1 h-4 w-0.5 bg-ink/60" style={{ left: `${elig.threshold * 100}%` }} title={t('ai.threshold', { pct: elig.threshold * 100 })} />
        </div>
        <div className="mt-1 text-[11px] opacity-80">{t('ai.threshold', { pct: elig.threshold * 100 })}</div>
      </div>

      {elig.helped.length > 0 && (
        <div>
          <h3 className="flex items-center gap-1.5 text-sm font-semibold">
            <TrendingUp className="size-4 text-forest-700" aria-hidden /> {t('ai.helped')}
          </h3>
          <ul className="mt-1.5 space-y-1 text-[13px] text-ink-soft">
            {elig.helped.map((f) => (
              <li key={f.key} className="flex gap-2">
                <CheckCircle2 className="mt-px size-4 shrink-0 text-forest-700" aria-hidden />
                {bi(f.label)}
              </li>
            ))}
          </ul>
        </div>
      )}

      {elig.held_back.length > 0 && (
        <div>
          <h3 className="flex items-center gap-1.5 text-sm font-semibold">
            <TrendingDown className="size-4 text-warn-700" aria-hidden /> {t('ai.heldBack')}
          </h3>
          <ul className="mt-1.5 divide-y divide-line text-[13px]">
            {elig.held_back.map((f) => (
              <li key={f.key} className="py-2">
                <div className="flex gap-2 text-ink">
                  <CircleDashed className="mt-px size-4 shrink-0 text-warn-700" aria-hidden />
                  {bi(f.label)}
                </div>
                <div className="mt-0.5 flex gap-1.5 pl-6 text-harvest-800">
                  <Lightbulb className="mt-px size-3.5 shrink-0" aria-hidden />
                  <span>{bi(f.tip)}</span>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="text-[11px] text-muted">
        {t('ai.modelCard', { model: elig.model.name, n: elig.model.trained_on.toLocaleString(), auc: Math.round(elig.model.auc * 100), real: elig.model.real_outcomes })}
        {elig.model.simulated && <> {t('ai.simulatedData')}</>}
      </p>
    </div>
  )
}
