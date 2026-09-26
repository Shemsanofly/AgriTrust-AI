import { Eye, Handshake, PiggyBank, Plus } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { ConfirmAction } from '../../components/ConfirmAction'
import { Badge, Button, Card, Dialog, EmptyState, ErrorNote, Field, Notice, ProgressBar, Skeleton, Stat, StatStrip, StatusBadge, cx, useToast } from '../../components/ui'
import { api } from '../../lib/api'
import { useApi, useBi, useErrorText, useFormat, type Bi } from '../../lib/hooks'

type Goal = { id: number; bucket: string; name: string; target_amount: number; saved_amount: number; due_date: string | null }
type Plan = { income_tzs: number; source: string; reason: Bi; buckets: { bucket: string; label: Bi; share: number; amount_tzs: number }[] }

const BUCKET_COLOR: Record<string, string> = { inputs: 'bg-forest-700', emergency: 'bg-earth-700', household: 'bg-info-700', goal: 'bg-harvest-500' }

export function SavingsTab() {
  const { t } = useTranslation()
  const bi = useBi()
  const f = useFormat()
  const toast = useToast()
  const errorText = useErrorText()
  const { data: plan } = useApi<Plan>('/savings/plan')
  const { data: goals, reload } = useApi<Goal[]>('/savings/goals')
  const [adding, setAdding] = useState(false)
  const [depositFor, setDepositFor] = useState<Goal | null>(null)
  const [amount, setAmount] = useState('')
  const [error, setError] = useState<string | null>(null)
  const total = (goals ?? []).reduce((s, g) => s + g.saved_amount, 0)
  const byBucket = (b: string) => (goals ?? []).filter((g) => g.bucket === b)

  const deposit = async (e: FormEvent) => {
    e.preventDefault()
    const n = Number(amount.replace(/[, ]/g, ''))
    if (!(n > 0) || !depositFor) return setError(t('validation.amount'))
    try {
      await api(`/savings/goals/${depositFor.id}`, { method: 'PATCH', body: { saved_amount: depositFor.saved_amount + n } })
      toast(t('savings.saved', { amount: f.tzs(n), goal: depositFor.name }))
      setDepositFor(null)
      setAmount('')
      reload()
    } catch (err) {
      setError(errorText(err))
    }
  }

  return (
    <div className="space-y-5">
      <StatStrip cols={4}>
        <Stat label={t('savings.current')} value={f.tzs(total)} sub={t('savings.acrossGoals', { count: goals?.length ?? 0 })} />
        <Stat label={t('savings.buckets.inputs')} value={f.tzs(byBucket('inputs').reduce((s, g) => s + g.saved_amount, 0))} sub={t('savings.nextSeason')} />
        <Stat label={t('savings.buckets.emergency')} value={f.tzs(byBucket('emergency').reduce((s, g) => s + g.saved_amount, 0))} />
        <Stat label={t('savings.buckets.goal')} value={f.tzs(byBucket('goal').reduce((s, g) => s + g.saved_amount, 0))} />
      </StatStrip>

      <div className="grid gap-5 lg:grid-cols-[1fr_1.2fr]">
        <Card title={t('savings.planTitle')} subtitle={plan ? bi(plan.reason) : undefined}>
          {!plan ? (
            <Skeleton className="h-28" />
          ) : plan.income_tzs <= 0 ? (
            <EmptyState compact title={t('savings.noIncome')} />
          ) : (
            <>
              <div className="flex h-3 overflow-hidden rounded-full" role="img" aria-label={t('savings.planTitle')}>
                {plan.buckets.map((b) => (
                  <div key={b.bucket} className={BUCKET_COLOR[b.bucket]} style={{ width: `${b.share * 100}%` }} />
                ))}
              </div>
              <ul className="mt-4 divide-y divide-line">
                {plan.buckets.map((b) => (
                  <li key={b.bucket} className="flex items-center gap-3 py-2 text-sm">
                    <span className={cx('size-2.5 rounded-full', BUCKET_COLOR[b.bucket])} aria-hidden />
                    <span className="flex-1">{bi(b.label)}</span>
                    <span className="num text-muted">{Math.round(b.share * 100)}%</span>
                    <span className="num w-28 text-right font-medium">{f.tzs(b.amount_tzs)}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-xs text-muted">{t('savings.planNote')}</p>
            </>
          )}
        </Card>

        <Card title={t('savings.goals')} actions={<Button size="sm" variant="secondary" icon={Plus} onClick={() => setAdding(true)}>{t('savings.addGoal')}</Button>}>
          {!goals ? (
            <Skeleton className="h-28" />
          ) : !goals.length ? (
            <EmptyState compact icon={PiggyBank} title={t('savings.noGoals')} body={t('savings.noGoalsBody')} />
          ) : (
            <ul className="-my-3 divide-y divide-line">
              {goals.map((g) => (
                <li key={g.id} className="py-3">
                  <div className="flex items-center justify-between gap-2 text-sm">
                    <span className="min-w-0">
                      <span className="font-medium">{g.name}</span> <span className="text-xs text-muted">· {t(`savings.buckets.${g.bucket}`)}</span>
                    </span>
                    <Button size="sm" variant="ghost" onClick={() => setDepositFor(g)}>
                      {t('savings.addMoney')}
                    </Button>
                  </div>
                  <div className="mt-1.5">
                    <ProgressBar value={g.saved_amount} max={g.target_amount} tone={g.saved_amount >= g.target_amount ? 'green' : 'gold'} label={g.name} />
                  </div>
                  <div className="num mt-1 flex justify-between text-xs text-muted">
                    <span>
                      {f.tzs(g.saved_amount)} / {f.tzs(g.target_amount)}
                    </span>
                    {g.due_date && <span>{t('savings.by', { date: f.date(g.due_date) })}</span>}
                  </div>
                </li>
              ))}
            </ul>
          )}
          <p className="mt-3 text-xs text-muted">{t('savings.futureLink')}</p>
        </Card>
      </div>

      <AddGoalDialog open={adding} onClose={() => setAdding(false)} onDone={() => (setAdding(false), reload())} />
      <Dialog open={depositFor != null} onClose={() => setDepositFor(null)} title={t('savings.addTo', { goal: depositFor?.name })}>
        <form onSubmit={deposit} className="space-y-4">
          <Field label={t('savings.amount')} hint={t('savings.recordHint')}>
            <input className="input num" inputMode="numeric" value={amount} onChange={(e) => setAmount(e.target.value)} />
          </Field>
          <ErrorNote text={error} />
          <Button type="submit" className="w-full">
            {t('savings.record')}
          </Button>
        </form>
      </Dialog>
    </div>
  )
}

function AddGoalDialog({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: () => void }) {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const [form, setForm] = useState({ bucket: 'goal', name: '', target: '', due: '' })
  const [error, setError] = useState<string | null>(null)
  const submit = async (e: FormEvent) => {
    e.preventDefault()
    const target = Number(form.target.replace(/[, ]/g, ''))
    if (form.name.trim().length < 2) return setError(t('validation.required'))
    if (!(target > 0)) return setError(t('validation.amount'))
    try {
      await api('/savings/goals', { method: 'POST', body: { bucket: form.bucket, name: form.name.trim(), target_amount: target, due_date: form.due || null } })
      setForm({ bucket: 'goal', name: '', target: '', due: '' })
      onDone()
    } catch (err) {
      setError(errorText(err))
    }
  }
  return (
    <Dialog open={open} onClose={onClose} title={t('savings.addGoal')}>
      <form onSubmit={submit} className="space-y-4">
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
          <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder={t('savings.goalPlaceholder')} />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label={t('savings.target')}>
            <input className="input num" inputMode="numeric" value={form.target} onChange={(e) => setForm({ ...form, target: e.target.value })} />
          </Field>
          <Field label={t('savings.dueDate')} optional>
            <input className="input" type="date" value={form.due} onChange={(e) => setForm({ ...form, due: e.target.value })} />
          </Field>
        </div>
        <ErrorNote text={error} />
        <Button type="submit" className="w-full">
          {t('common.save')}
        </Button>
      </form>
    </Dialog>
  )
}

/* ------------------------------------------------------------------ data sharing */

const CATEGORIES = ['profile', 'production', 'storage', 'sales', 'receipts'] as const

export function SharingTab() {
  const { t } = useTranslation()
  const f = useFormat()
  const toast = useToast()
  const { data: consents, reload } = useApi<any[]>('/consents')
  const { data: access } = useApi<any[]>('/farmers/me/access-history')
  const { data: lenders } = useApi<{ id: number; name: string }[]>('/partners?role=LENDER')
  const { data: insurers } = useApi<{ id: number; name: string }[]>('/partners?role=INSURER')
  const partners = [...(lenders ?? []), ...(insurers ?? [])]
  const [form, setForm] = useState({ grantee: '', purpose: '', days: '90', categories: ['profile'] as string[] })
  const [confirm, setConfirm] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const grantee = partners.find((p) => String(p.id) === form.grantee) ?? partners[0]
  const toggle = (c: string) => setForm({ ...form, categories: form.categories.includes(c) ? form.categories.filter((x) => x !== c) : [...form.categories, c] })

  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_1.1fr]">
      <div className="space-y-5">
        <Notice tone="info" title={t('consent.youDecide')}>
          {t('consent.explainer')}
        </Notice>
        <Card title={t('consent.grantTitle')}>
          <form
            onSubmit={(e) => {
              e.preventDefault()
              if (form.purpose.trim().length < 3) return setError(t('validation.purpose'))
              if (!form.categories.length) return setError(t('validation.categories'))
              setError(null)
              setConfirm(true)
            }}
            className="space-y-4"
          >
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
                {CATEGORIES.map((c) => {
                  const on = form.categories.includes(c)
                  return (
                    <label key={c} className={cx('flex min-h-10 cursor-pointer items-center gap-2 rounded-md border px-3 text-sm', on ? 'border-forest-700 bg-forest-50' : 'border-line-strong')}>
                      <input type="checkbox" className="accent-forest-800" checked={on} onChange={() => toggle(c)} />
                      {t(`consent.categories.${c}`)}
                    </label>
                  )
                })}
              </div>
            </fieldset>
            <div className="grid grid-cols-[1fr_6rem] gap-3">
              <Field label={t('consent.why')}>
                <input className="input" value={form.purpose} onChange={(e) => setForm({ ...form, purpose: e.target.value })} placeholder={t('consent.purposePlaceholder')} />
              </Field>
              <Field label={t('consent.days')}>
                <input className="input num" type="number" min={1} max={365} value={form.days} onChange={(e) => setForm({ ...form, days: e.target.value })} />
              </Field>
            </div>
            <ErrorNote text={error} />
            <Button type="submit" icon={Handshake}>
              {t('consent.grant')}
            </Button>
          </form>
        </Card>
      </div>

      <div className="space-y-5">
        <Card title={t('consent.listTitle')}>
          {!consents ? (
            <Skeleton className="h-20" />
          ) : !consents.length ? (
            <EmptyState compact title={t('consent.none')} />
          ) : (
            <ul className="-my-3 divide-y divide-line">
              {consents.map((c) => (
                <li key={c.id} className="flex flex-wrap items-start gap-3 py-3">
                  <div className="min-w-0 flex-1 text-sm">
                    <div className="flex flex-wrap items-center gap-2 font-medium">
                      {c.grantee?.name} <StatusBadge status={c.state} />
                    </div>
                    <div className="text-[13px] text-muted">{c.data_categories.map((x: string) => t(`consent.categories.${x}`)).join(' · ')}</div>
                    <div className="text-xs text-muted">
                      {c.purpose} · {c.state === 'ACTIVE' ? t('consent.until', { date: f.date(c.expires_at) }) : f.date(c.revoked_at ?? c.expires_at)}
                    </div>
                  </div>
                  {c.state === 'ACTIVE' && (
                    <Button
                      size="sm"
                      variant="danger"
                      onClick={async () => {
                        await api(`/consents/${c.id}`, { method: 'DELETE' })
                        toast(t('consent.revoked'))
                        reload()
                      }}
                    >
                      {t('consent.revoke')}
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title={t('consent.accessHistory')} actions={<Eye className="size-4 text-muted" aria-hidden />}>
          {!access ? (
            <Skeleton className="h-16" />
          ) : !access.length ? (
            <EmptyState compact title={t('consent.noAccess')} />
          ) : (
            <ul className="-my-2 divide-y divide-line text-sm">
              {access.slice(0, 12).map((a) => (
                <li key={a.id} className="py-2">
                  <div>
                    <span className="font-medium">{a.actor_name}</span> <Badge>{t(`roles.${a.actor_role}`)}</Badge>
                  </div>
                  <div className="text-xs text-muted">
                    {t(`consent.accessAction.${a.action}`, { defaultValue: a.action })} · {f.dateTime(a.ts)}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <ConfirmAction
        open={confirm}
        title={t('consent.confirmTitle')}
        summary={[
          [t('consent.who'), grantee?.name],
          [t('consent.what'), form.categories.map((c) => t(`consent.categories.${c}`)).join(', ')],
          [t('consent.why'), form.purpose],
          [t('consent.days'), form.days],
        ]}
        note={t('consent.confirmNote')}
        confirmLabel={t('consent.grant')}
        onClose={() => setConfirm(false)}
        onConfirm={async (pin) => {
          await api('/consents', { method: 'POST', body: { grantee_user_id: grantee?.id, data_categories: form.categories, purpose: form.purpose.trim(), days: Number(form.days) || 90, confirm_pin: pin } })
          setForm({ ...form, purpose: '' })
          toast(t('consent.granted'))
          reload()
        }}
      />
    </div>
  )
}
