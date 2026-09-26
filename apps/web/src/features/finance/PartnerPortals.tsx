import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { AlertsPanel } from '../../components/AlertsPanel'
import { Button, Card, Empty, ErrorNote, Field, Loading, SimulatedTag, StatusBadge } from '../../components/ui'
import { api } from '../../lib/api'
import { useApi, useErrorText, useFormat } from '../../lib/hooks'
import { ProfileView } from './ProfileView'

export function LenderPortal() {
  const { t } = useTranslation()
  const f = useFormat()
  const { data, loading, reload } = useApi<any[]>('/loans')
  const [selected, setSelected] = useState<number | null>(null)

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-xl font-bold">💰 {t('lender.title')}</h1>
        <SimulatedTag label={t('loans.simulatedLender')} />
      </div>
      <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">⚖️ {t('lender.humanOnly')}</p>
      {loading && !data ? (
        <Loading />
      ) : !data?.length ? (
        <Empty>{t('loans.none')}</Empty>
      ) : (
        <div className="grid gap-2">
          {data.map((l) => (
            <button
              key={l.id}
              onClick={() => setSelected(l.id === selected ? null : l.id)}
              className={`flex flex-wrap items-center justify-between gap-2 rounded-2xl border bg-white p-3 text-left text-sm ${selected === l.id ? 'border-brand-600' : 'border-stone-200'}`}
            >
              <span>
                <b>#{l.id}</b> · {l.farmer?.display_name} ({l.farmer?.public_id}) · {f.tzs(l.amount)} · {l.purpose}
              </span>
              <StatusBadge status={l.status} />
            </button>
          ))}
        </div>
      )}
      {selected && <LoanReview key={selected} loanId={selected} onDecided={reload} />}
      <AlertsPanel />
    </div>
  )
}

function LoanReview({ loanId, onDecided }: { loanId: number; onDecided: () => void }) {
  const { t } = useTranslation()
  const f = useFormat()
  const errorText = useErrorText()
  const { data, loading, reload } = useApi<any>(`/loans/${loanId}`)
  const [form, setForm] = useState({ status: 'APPROVED', reason: '', interest_rate_pct: '18', tenor_months: '6' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const decide = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api(`/loans/${loanId}/decision`, {
        method: 'PATCH',
        body: { status: form.status, reason: form.reason || null, interest_rate_pct: Number(form.interest_rate_pct), tenor_months: Number(form.tenor_months) },
      })
      reload()
      onDecided()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  if (loading && !data) return <Loading />
  if (!data) return null
  return (
    <div className="space-y-4">
      <Card title={t('lender.application', { id: data.id })}>
        <p className="text-sm">
          {data.farmer.display_name} · {f.tzs(data.amount)} · {data.purpose} · {t('loans.repaymentMonth')}: {data.repayment_month ?? '—'}
        </p>
        {data.consent && (
          <p className="mt-1 text-xs text-stone-500">
            🤝 {t('lender.consent', { state: t(`status.${data.consent.state}`), date: f.date(data.consent.expires_at) })}
          </p>
        )}
      </Card>
      {data.profile ? <ProfileView profile={data.profile} /> : <Empty>🔒 {t('lender.noConsent')}</Empty>}
      <Card title={`🧑‍⚖️ ${t('lender.decision')}`}>
        <form onSubmit={decide} className="grid gap-3 sm:grid-cols-2">
          <Field label={t('lender.status')}>
            <select className="input" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
              {['UNDER_REVIEW', 'APPROVED', 'DECLINED', 'DISBURSED', 'REPAYING', 'CLOSED'].map((s) => (
                <option key={s} value={s}>
                  {t(`status.${s}`)}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t('lender.reason')} hint={t('lender.reasonHint')}>
            <input className="input" value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} />
          </Field>
          {form.status === 'APPROVED' && (
            <>
              <Field label={t('lender.rate')}>
                <input className="input" inputMode="decimal" value={form.interest_rate_pct} onChange={(e) => setForm({ ...form, interest_rate_pct: e.target.value })} />
              </Field>
              <Field label={t('lender.tenor')}>
                <input className="input" inputMode="numeric" value={form.tenor_months} onChange={(e) => setForm({ ...form, tenor_months: e.target.value })} />
              </Field>
            </>
          )}
          <div className="sm:col-span-2">
            <ErrorNote text={error} />
            <Button type="submit" busy={busy}>
              {t('lender.record')}
            </Button>
          </div>
        </form>
        {data.decision_reason && (
          <p className="mt-3 text-sm text-stone-600">
            {t('loans.humanDecision', { name: data.decided_by_name })}: “{data.decision_reason}” · {f.dateTime(data.decided_at)}
          </p>
        )}
      </Card>
    </div>
  )
}

export function InsurerPortal() {
  const { t } = useTranslation()
  const f = useFormat()
  const errorText = useErrorText()
  const { data, loading, reload } = useApi<any[]>('/insurance/policies')
  const [reasons, setReasons] = useState<Record<number, string>>({})
  const [profile, setProfile] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)

  const run = async (fn: () => Promise<unknown>) => {
    setError(null)
    try {
      await fn()
      reload()
    } catch (err) {
      setError(errorText(err))
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-xl font-bold">🛡️ {t('insurer.title')}</h1>
        <SimulatedTag label={t('insurance.simulatedInsurer')} />
      </div>
      <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">⚖️ {t('insurer.humanOnly')}</p>
      <ErrorNote text={error} />
      {loading && !data ? (
        <Loading />
      ) : !data?.length ? (
        <Empty>{t('insurance.noPolicies')}</Empty>
      ) : (
        data.map((p) => (
          <Card key={p.id}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <b>
                #{p.id} · {t(`products.${p.product}`)} · {p.farmer?.display_name} ({p.farmer?.region})
              </b>
              <StatusBadge status={p.status} />
            </div>
            <p className="text-sm text-stone-600">
              {t('insurance.coverage')}: {f.tzs(p.coverage_tzs)} · {t('insurance.premium')}: {f.tzs(p.premium_tzs)}
              {p.rainfall_threshold_mm && ` · ${t('insurance.threshold', { mm: p.rainfall_threshold_mm })}`}
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              {p.status === 'REQUESTED' && (
                <>
                  <Button className="min-h-8 px-3 text-xs" onClick={() => run(() => api(`/insurance/policies/${p.id}`, { method: 'PATCH', body: { status: 'ACTIVE' } }))}>
                    {t('insurer.activate')}
                  </Button>
                  <Button variant="secondary" className="min-h-8 px-3 text-xs" onClick={() => run(() => api(`/insurance/policies/${p.id}`, { method: 'PATCH', body: { status: 'DECLINED' } }))}>
                    {t('insurer.decline')}
                  </Button>
                </>
              )}
              {p.status === 'ACTIVE' && p.product === 'weather_index' && (
                <Button variant="secondary" className="min-h-8 px-3 text-xs" onClick={() => run(() => api(`/insurance/policies/${p.id}/check-trigger`, { method: 'POST' }))}>
                  🌧️ {t('insurance.checkTrigger')}
                </Button>
              )}
              <Button variant="ghost" className="min-h-8 px-3 text-xs" onClick={() => run(async () => setProfile(await api(`/farmers/${p.farmer.public_id}/profile`)))}>
                {t('insurer.viewProfile')}
              </Button>
            </div>
            {p.claims.map((c: any) => (
              <div key={c.id} className="mt-3 rounded-xl bg-stone-50 p-3 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  🛡️ <b>{t('insurance.claim')} #{c.id}</b> · {t(`insurance.triggerTypes.${c.trigger_type}`)} <StatusBadge status={c.status} />
                </div>
                {c.evidence?.rainfall_mm != null && (
                  <p className="text-stone-600">
                    {t('insurance.rainfall', { mm: c.evidence.rainfall_mm, threshold: c.evidence.threshold_mm })} {c.evidence.simulated && <SimulatedTag />}
                  </p>
                )}
                {c.evidence?.description && <p className="text-stone-600">“{c.evidence.description}”</p>}
                {c.decision_reason ? (
                  <p className="mt-1">🧑‍⚖️ “{c.decision_reason}”</p>
                ) : (
                  <div className="mt-2 flex flex-wrap gap-2">
                    <input className="input max-w-xs" placeholder={t('lender.reason')} value={reasons[c.id] ?? ''} onChange={(e) => setReasons({ ...reasons, [c.id]: e.target.value })} />
                    {['APPROVED', 'REJECTED'].map((s) => (
                      <Button
                        key={s}
                        variant={s === 'APPROVED' ? 'primary' : 'danger'}
                        className="min-h-8 px-3 text-xs"
                        onClick={() => run(() => api(`/insurance/claims/${c.id}/decision`, { method: 'PATCH', body: { status: s, reason: reasons[c.id] || null } }))}
                      >
                        {t(`status.${s}`)}
                      </Button>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </Card>
        ))
      )}
      {profile && (
        <div>
          <div className="mb-2 flex justify-end">
            <Button variant="ghost" onClick={() => setProfile(null)}>
              {t('common.close')}
            </Button>
          </div>
          <ProfileView profile={profile} />
        </div>
      )}
      <AlertsPanel />
    </div>
  )
}
