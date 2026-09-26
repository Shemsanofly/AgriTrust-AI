import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { PinDialog } from '../../components/PinDialog'
import { Badge, Button, Card, Empty, ErrorNote, Field, Loading, SimulatedTag, StatusBadge, Tabs } from '../../components/ui'
import { api } from '../../lib/api'
import { useApi, useBi, useErrorText, useFormat, type Bi } from '../../lib/hooks'
import { ProfileView, type Profile } from './ProfileView'

type Tab = 'profile' | 'consent' | 'loans' | 'insurance' | 'savings'
const CATEGORIES = ['profile', 'production', 'storage', 'sales', 'receipts'] as const

/** Runs an action that needs PIN step-up: opens the dialog, then calls fn(pin). */
function usePinAction() {
  const errorText = useErrorText()
  const [pending, setPending] = useState<{ title: string; fn: (pin: string) => Promise<unknown> } | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const dialog = (
    <PinDialog
      open={pending != null}
      busy={busy}
      title={pending?.title ?? ''}
      onCancel={() => setPending(null)}
      onConfirm={async (pin) => {
        if (!pending) return
        setBusy(true)
        setError(null)
        try {
          await pending.fn(pin)
          setPending(null)
        } catch (err) {
          setError(errorText(err))
          setPending(null)
        } finally {
          setBusy(false)
        }
      }}
    />
  )
  return { ask: (title: string, fn: (pin: string) => Promise<unknown>) => setPending({ title, fn }), dialog, error, setError }
}

export function KifedhaPage() {
  const { t } = useTranslation()
  const [tab, setTab] = useState<Tab>('profile')
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">💰 {t('kifedha.title')}</h1>
      <Tabs
        value={tab}
        onChange={setTab}
        tabs={[
          { id: 'profile', label: t('kifedha.tabs.profile') },
          { id: 'consent', label: t('kifedha.tabs.consent') },
          { id: 'loans', label: t('kifedha.tabs.loans') },
          { id: 'insurance', label: t('kifedha.tabs.insurance') },
          { id: 'savings', label: t('kifedha.tabs.savings') },
        ]}
      />
      {tab === 'profile' && <MyProfile />}
      {tab === 'consent' && <Consents />}
      {tab === 'loans' && <Loans />}
      {tab === 'insurance' && <Insurance />}
      {tab === 'savings' && <Savings />}
    </div>
  )
}

function MyProfile() {
  const { t } = useTranslation()
  const f = useFormat()
  const errorText = useErrorText()
  const { data, loading } = useApi<Profile>('/farmers/me/profile')
  const { data: access } = useApi<any[]>('/farmers/me/access-history')
  const [contest, setContest] = useState('')
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    try {
      await api('/farmers/me/profile/contest', { method: 'POST', body: { description: contest } })
      setSent(true)
      setContest('')
    } catch (err) {
      setError(errorText(err))
    }
  }

  if (loading && !data) return <Loading />
  return (
    <div className="space-y-4">
      {data && <ProfileView profile={data} />}
      <Card title={`✋ ${t('profile.contestTitle')}`}>
        {sent ? (
          <p className="text-sm text-green-700">✅ {t('profile.contestSent')}</p>
        ) : (
          <form onSubmit={submit} className="space-y-2">
            <textarea className="input min-h-20" value={contest} onChange={(e) => setContest(e.target.value)} placeholder={t('profile.contestPlaceholder')} minLength={5} required />
            <Button type="submit" variant="secondary">
              {t('profile.contestSend')}
            </Button>
          </form>
        )}
        <ErrorNote text={error} />
      </Card>
      <Card title={`👁️ ${t('profile.accessHistory')}`}>
        {!access?.length ? (
          <Empty>{t('profile.noAccess')}</Empty>
        ) : (
          <ul className="divide-y divide-stone-100 text-sm">
            {access.map((a) => (
              <li key={a.id} className="py-2">
                <b>{a.actor_name}</b> ({t(`roles.${a.actor_role}`)}) · {a.action} {a.resource_type} · {f.dateTime(a.ts)}
                {a.reason && <div className="text-xs text-stone-500">{a.reason}</div>}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}

function Consents() {
  const { t } = useTranslation()
  const f = useFormat()
  const { data, reload } = useApi<any[]>('/consents')
  const { data: lenders } = useApi<{ id: number; name: string }[]>('/partners?role=LENDER')
  const { data: insurers } = useApi<{ id: number; name: string }[]>('/partners?role=INSURER')
  const partners = [...(lenders ?? []), ...(insurers ?? [])]
  const [form, setForm] = useState({ grantee: '', purpose: '', days: '90', categories: ['profile'] as string[] })
  const { ask, dialog, error } = usePinAction()

  const grant = (e: FormEvent) => {
    e.preventDefault()
    ask(t('pin.confirmConsent'), async (pin) => {
      await api('/consents', {
        method: 'POST',
        body: { grantee_user_id: Number(form.grantee || partners[0]?.id), data_categories: form.categories, purpose: form.purpose, days: Number(form.days), confirm_pin: pin },
      })
      setForm({ ...form, purpose: '' })
      reload()
    })
  }
  const toggle = (c: string) => setForm({ ...form, categories: form.categories.includes(c) ? form.categories.filter((x) => x !== c) : [...form.categories, c] })

  return (
    <div className="space-y-4">
      <p className="rounded-xl bg-sky-50 p-3 text-sm text-sky-900">🔐 {t('consent.explainer')}</p>
      <Card title={t('consent.grantTitle')}>
        <form onSubmit={grant} className="space-y-3">
          <Field label={t('consent.who')}>
            <select className="input" value={form.grantee} onChange={(e) => setForm({ ...form, grantee: e.target.value })}>
              {partners.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </Field>
          <fieldset>
            <legend className="label">{t('consent.what')}</legend>
            <div className="flex flex-wrap gap-2">
              {CATEGORIES.map((c) => (
                <label key={c} className={`cursor-pointer rounded-full border px-3 py-1 text-sm ${form.categories.includes(c) ? 'border-brand-700 bg-brand-50' : 'border-stone-300'}`}>
                  <input type="checkbox" className="sr-only" checked={form.categories.includes(c)} onChange={() => toggle(c)} />
                  {t(`consent.categories.${c}`)}
                </label>
              ))}
            </div>
          </fieldset>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t('consent.why')}>
              <input className="input" value={form.purpose} onChange={(e) => setForm({ ...form, purpose: e.target.value })} required minLength={3} />
            </Field>
            <Field label={t('consent.days')}>
              <input className="input" type="number" min={1} max={365} value={form.days} onChange={(e) => setForm({ ...form, days: e.target.value })} />
            </Field>
          </div>
          <Button type="submit" disabled={!form.categories.length}>
            🤝 {t('consent.grant')}
          </Button>
        </form>
        <ErrorNote text={error} />
      </Card>
      <Card title={t('consent.listTitle')}>
        {!data?.length ? (
          <Empty>{t('consent.none')}</Empty>
        ) : (
          <ul className="space-y-2">
            {data.map((c) => (
              <li key={c.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-stone-50 p-3 text-sm">
                <div>
                  <div className="font-semibold">
                    {c.grantee?.name} <StatusBadge status={c.state} />
                  </div>
                  <div className="text-stone-600">{c.data_categories.map((x: string) => t(`consent.categories.${x}`)).join(', ')}</div>
                  <div className="text-xs text-stone-500">
                    {c.purpose} · {t('consent.until')} {f.date(c.expires_at)}
                  </div>
                </div>
                {c.state === 'ACTIVE' && (
                  <Button variant="danger" className="min-h-8 px-3 text-xs" onClick={() => api(`/consents/${c.id}`, { method: 'DELETE' }).then(reload)}>
                    {t('consent.revoke')}
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>
      {dialog}
    </div>
  )
}

function Loans() {
  const { t } = useTranslation()
  const f = useFormat()
  const { data, reload } = useApi<any[]>('/loans')
  const { data: lenders } = useApi<{ id: number; name: string }[]>('/partners?role=LENDER')
  const { data: profile } = useApi<Profile>('/farmers/me/profile')
  const suggestion = profile?.suggested_products.find((p) => p.type === 'input_loan')
  const [form, setForm] = useState({ lender: '', amount: '', purpose: '', repayment_month: '' })
  const { ask, dialog, error } = usePinAction()

  const apply = (e: FormEvent) => {
    e.preventDefault()
    ask(t('pin.confirmLoan'), async (pin) => {
      await api('/loans', {
        method: 'POST',
        body: {
          lender_user_id: Number(form.lender || lenders?.[0]?.id),
          amount: Number(form.amount),
          purpose: form.purpose,
          repayment_month: form.repayment_month || suggestion?.repayment_month || null,
          confirm_pin: pin,
        },
      })
      setForm({ lender: '', amount: '', purpose: '', repayment_month: '' })
      reload()
    })
  }

  return (
    <div className="space-y-4">
      <Card title={t('loans.applyTitle')} actions={<SimulatedTag label={t('loans.simulatedLender')} />}>
        {suggestion && (
          <p className="mb-3 rounded-lg bg-green-50 px-3 py-2 text-sm">
            💡 {t('loans.suggestion', { amount: f.tzs(suggestion.max_amount_tzs), month: suggestion.repayment_month })}
          </p>
        )}
        <form onSubmit={apply} className="grid gap-3 sm:grid-cols-2">
          <Field label={t('loans.lender')}>
            <select className="input" value={form.lender} onChange={(e) => setForm({ ...form, lender: e.target.value })}>
              {lenders?.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t('loans.amount')}>
            <input className="input" inputMode="numeric" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} required />
          </Field>
          <Field label={t('loans.purpose')}>
            <input className="input" value={form.purpose} onChange={(e) => setForm({ ...form, purpose: e.target.value })} required minLength={3} placeholder={t('loans.purposePlaceholder')} />
          </Field>
          <Field label={t('loans.repaymentMonth')}>
            <input className="input" type="month" value={form.repayment_month || suggestion?.repayment_month || ''} onChange={(e) => setForm({ ...form, repayment_month: e.target.value })} />
          </Field>
          <div className="sm:col-span-2">
            <p className="mb-2 text-xs text-stone-500">{t('loans.consentNote')}</p>
            <Button type="submit">{t('loans.submit')}</Button>
          </div>
        </form>
        <ErrorNote text={error} />
      </Card>
      <Card title={t('loans.myApplications')}>
        {!data?.length ? (
          <Empty>{t('loans.none')}</Empty>
        ) : (
          <ul className="space-y-2">
            {data.map((l) => (
              <li key={l.id} className="rounded-xl bg-stone-50 p-3 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <b>
                    #{l.id} · {f.tzs(l.amount)}
                  </b>
                  <StatusBadge status={l.status} />
                </div>
                <div className="text-stone-600">
                  {l.purpose} · {l.lender?.name}
                </div>
                {l.decision_reason && (
                  <div className="mt-1">
                    🧑‍⚖️ {t('loans.humanDecision', { name: l.decided_by_name })}: “{l.decision_reason}”
                  </div>
                )}
                {l.terms?.interest_rate_pct && (
                  <div className="text-xs text-stone-500">
                    {t('loans.terms', { rate: l.terms.interest_rate_pct, months: l.terms.tenor_months })}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>
      {dialog}
    </div>
  )
}

function Insurance() {
  const { t } = useTranslation()
  const bi = useBi()
  const f = useFormat()
  const errorText = useErrorText()
  const { data: recs } = useApi<{ recommendations: any[] }>('/insurance/recommendations')
  const { data: policies, reload } = useApi<any[]>('/insurance/policies')
  const { data: insurers } = useApi<{ id: number; name: string }[]>('/partners?role=INSURER')
  const { ask, dialog, error } = usePinAction()
  const [trigger, setTrigger] = useState<Record<number, any>>({})
  const [err, setErr] = useState<string | null>(null)

  const request = (rec: any) =>
    ask(t('pin.confirmInsurance'), async (pin) => {
      await api('/insurance/policies', {
        method: 'POST',
        body: { insurer_user_id: insurers?.[0]?.id, product: rec.product, coverage_tzs: rec.suggested_coverage_tzs, farm_id: rec.farm_id ?? null, confirm_pin: pin },
      })
      reload()
    })

  const check = async (id: number) => {
    setErr(null)
    try {
      const r = await api(`/insurance/policies/${id}/check-trigger`, { method: 'POST' })
      setTrigger({ ...trigger, [id]: r })
      reload()
    } catch (e) {
      setErr(errorText(e))
    }
  }

  return (
    <div className="space-y-4">
      <Card title={t('insurance.recommendations')} actions={<SimulatedTag label={t('insurance.simulatedInsurer')} />}>
        {!recs?.recommendations.length ? (
          <Empty>{t('insurance.noRecs')}</Empty>
        ) : (
          <ul className="space-y-2">
            {recs.recommendations.map((r, i) => (
              <li key={i} className="rounded-xl bg-stone-50 p-3 text-sm">
                <div className="flex flex-wrap items-center gap-2 font-semibold">
                  {t(`products.${r.product}`)} <Badge tone={r.priority === 'HIGH' ? 'red' : 'amber'}>{t(`priority.${r.priority}`)}</Badge>
                </div>
                <p className="text-stone-700">{bi(r.reason as Bi)}</p>
                <p className="text-stone-600">
                  {t('insurance.coverage')}: {f.tzs(r.suggested_coverage_tzs)} · {t('insurance.premium')}: ~{f.tzs(r.indicative_premium_tzs)}
                </p>
                <Button className="mt-2 min-h-8 px-3 text-xs" onClick={() => request(r)}>
                  {t('insurance.request')}
                </Button>
              </li>
            ))}
          </ul>
        )}
        <ErrorNote text={error} />
      </Card>
      <Card title={t('insurance.myPolicies')}>
        <ErrorNote text={err} />
        {!policies?.length ? (
          <Empty>{t('insurance.noPolicies')}</Empty>
        ) : (
          <ul className="space-y-2">
            {policies.map((p) => (
              <li key={p.id} className="rounded-xl bg-stone-50 p-3 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <b>
                    #{p.id} · {t(`products.${p.product}`)}
                  </b>
                  <StatusBadge status={p.status} />
                </div>
                <div className="text-stone-600">
                  {f.tzs(p.coverage_tzs)} · {p.insurer?.name}
                  {p.rainfall_threshold_mm && ` · ${t('insurance.threshold', { mm: p.rainfall_threshold_mm })}`}
                </div>
                {p.product === 'weather_index' && p.status === 'ACTIVE' && (
                  <Button variant="secondary" className="mt-2 min-h-8 px-3 text-xs" onClick={() => check(p.id)}>
                    🌧️ {t('insurance.checkTrigger')}
                  </Button>
                )}
                {trigger[p.id] && (
                  <p className="mt-2 text-sm">
                    {t('insurance.rainfall', { mm: trigger[p.id].rainfall_mm, threshold: trigger[p.id].threshold_mm })}{' '}
                    {trigger[p.id].simulated && <SimulatedTag />} → {trigger[p.id].triggered ? `⚠️ ${t('insurance.triggered')}` : `✅ ${t('insurance.notTriggered')}`}
                  </p>
                )}
                {p.claims.map((c: any) => (
                  <div key={c.id} className="mt-2 rounded-lg bg-white p-2">
                    🛡️ {t('insurance.claim')} #{c.id} · {t(`insurance.triggerTypes.${c.trigger_type}`)} <StatusBadge status={c.status} />
                    {c.decision_reason && <div className="text-xs text-stone-600">“{c.decision_reason}”</div>}
                  </div>
                ))}
              </li>
            ))}
          </ul>
        )}
        <p className="mt-2 text-xs text-stone-500">{t('insurance.humanNote')}</p>
      </Card>
      {dialog}
    </div>
  )
}

function Savings() {
  const { t } = useTranslation()
  const bi = useBi()
  const f = useFormat()
  const { data: plan } = useApi<any>('/savings/plan')
  const { data: goals, reload } = useApi<any[]>('/savings/goals')
  const [form, setForm] = useState({ bucket: 'goal', name: '', target_amount: '' })
  const [add, setAdd] = useState<Record<number, string>>({})

  const create = async (e: FormEvent) => {
    e.preventDefault()
    await api('/savings/goals', { method: 'POST', body: { ...form, target_amount: Number(form.target_amount) } })
    setForm({ bucket: 'goal', name: '', target_amount: '' })
    reload()
  }
  const deposit = async (goal: any) => {
    const amount = Number(add[goal.id] || 0)
    if (!amount) return
    await api(`/savings/goals/${goal.id}`, { method: 'PATCH', body: { saved_amount: goal.saved_amount + amount } })
    setAdd({ ...add, [goal.id]: '' })
    reload()
  }

  return (
    <div className="space-y-4">
      {plan && (
        <Card title={`🧮 ${t('savings.planTitle')}`} actions={<Badge tone="blue">{t('farm.rulesModel')}</Badge>}>
          <p className="mb-3 text-sm text-stone-600">{bi(plan.reason)}</p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {plan.buckets.map((b: any) => (
              <div key={b.bucket} className="rounded-xl bg-stone-50 p-3">
                <div className="text-lg">{{ inputs: '🌱', emergency: '🛟', household: '🏠', goal: '🎯' }[b.bucket as string]}</div>
                <div className="text-xs text-stone-500">{bi(b.label)}</div>
                <div className="font-semibold">{f.tzs(b.amount_tzs)}</div>
                <div className="text-xs text-stone-500">{Math.round(b.share * 100)}%</div>
              </div>
            ))}
          </div>
          <p className="mt-2 text-xs text-stone-500">{t('savings.futureLink')}</p>
        </Card>
      )}
      <Card title={t('savings.goals')}>
        <form onSubmit={create} className="mb-3 grid gap-2 sm:grid-cols-4 sm:items-end">
          <Field label={t('savings.bucket')}>
            <select className="input" value={form.bucket} onChange={(e) => setForm({ ...form, bucket: e.target.value })}>
              {['inputs', 'emergency', 'household', 'goal'].map((b) => (
                <option key={b} value={b}>
                  {t(`savings.buckets.${b}`)}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t('savings.goalName')}>
            <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required placeholder={t('savings.goalPlaceholder')} />
          </Field>
          <Field label={t('savings.target')}>
            <input className="input" inputMode="numeric" value={form.target_amount} onChange={(e) => setForm({ ...form, target_amount: e.target.value })} required />
          </Field>
          <Button type="submit">+ {t('savings.addGoal')}</Button>
        </form>
        {!goals?.length ? (
          <Empty>{t('savings.noGoals')}</Empty>
        ) : (
          <ul className="space-y-2">
            {goals.map((g) => {
              const pct = Math.min(100, Math.round((g.saved_amount / g.target_amount) * 100))
              return (
                <li key={g.id} className="rounded-xl bg-stone-50 p-3 text-sm">
                  <div className="flex justify-between">
                    <b>{g.name}</b>
                    <span>
                      {f.tzs(g.saved_amount)} / {f.tzs(g.target_amount)}
                    </span>
                  </div>
                  <div className="mt-1 h-2 rounded-full bg-stone-200">
                    <div className="h-2 rounded-full bg-brand-600" style={{ width: `${pct}%` }} />
                  </div>
                  <div className="mt-2 flex gap-2">
                    <input className="input max-w-40" inputMode="numeric" placeholder={t('savings.addAmount')} value={add[g.id] ?? ''} onChange={(e) => setAdd({ ...add, [g.id]: e.target.value })} />
                    <Button variant="secondary" onClick={() => deposit(g)}>
                      {t('savings.save')}
                    </Button>
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </Card>
    </div>
  )
}
