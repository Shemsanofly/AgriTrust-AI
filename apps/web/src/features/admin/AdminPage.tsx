import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { Badge, Button, Card, Empty, ErrorNote, Field, Tabs } from '../../components/ui'
import { api } from '../../lib/api'
import { useApi, useBi, useErrorText, useFormat } from '../../lib/hooks'

type Tab = 'alerts' | 'audit' | 'users' | 'sms' | 'demo'

export function AdminPage() {
  const { t } = useTranslation()
  const [tab, setTab] = useState<Tab>('alerts')
  const { data: ledger } = useApi<{ mode: string; simulated_ledger_intact: boolean | null }>('/admin/ledger')
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-bold">🛠️ {t('admin.title')}</h1>
        {ledger && (
          <Badge tone={ledger.simulated_ledger_intact === false ? 'red' : 'green'}>
            🔗 {ledger.mode === 'ONCHAIN' ? t('verify.onchain') : t('verify.simulatedLedger')}
            {ledger.simulated_ledger_intact != null && ` · ${ledger.simulated_ledger_intact ? t('admin.ledgerIntact') : t('admin.ledgerBroken')}`}
          </Badge>
        )}
      </div>
      <Tabs
        value={tab}
        onChange={setTab}
        tabs={[
          { id: 'alerts', label: t('admin.tabs.alerts') },
          { id: 'audit', label: t('admin.tabs.audit') },
          { id: 'users', label: t('admin.tabs.users') },
          { id: 'sms', label: t('admin.tabs.sms') },
          { id: 'demo', label: t('admin.tabs.demo') },
        ]}
      />
      {tab === 'alerts' && <AdminAlerts />}
      {tab === 'audit' && <Audit />}
      {tab === 'users' && <Users />}
      {tab === 'sms' && <Sms />}
      {tab === 'demo' && <TamperDemo />}
    </div>
  )
}

function AdminAlerts() {
  const { t } = useTranslation()
  const bi = useBi()
  const f = useFormat()
  const { data } = useApi<any[]>('/admin/alerts')
  return (
    <Card title={t('admin.fraudAlerts')}>
      {!data?.length ? (
        <Empty>{t('alerts.none')}</Empty>
      ) : (
        <ul className="divide-y divide-stone-100 text-sm">
          {data.map((a) => (
            <li key={a.id} className="py-2">
              <Badge tone={a.severity === 'WARNING' ? 'amber' : a.severity === 'CRITICAL' ? 'red' : 'stone'}>{a.kind}</Badge> {bi(a.message)}
              <div className="text-xs text-stone-500">{f.dateTime(a.created_at)}</div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

function Audit() {
  const { t } = useTranslation()
  const f = useFormat()
  const { data } = useApi<any[]>('/admin/audit')
  return (
    <Card title={t('admin.auditLog')}>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-xs text-stone-500">
            <tr>
              <th className="py-1 pr-3">{t('admin.when')}</th>
              <th className="py-1 pr-3">{t('admin.who')}</th>
              <th className="py-1 pr-3">{t('admin.action')}</th>
              <th className="py-1 pr-3">{t('admin.resource')}</th>
              <th className="py-1">{t('admin.why')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-stone-100">
            {data?.map((r) => (
              <tr key={r.id}>
                <td className="py-1 pr-3 whitespace-nowrap">{f.dateTime(r.ts)}</td>
                <td className="py-1 pr-3">{r.actor_name ?? '—'}</td>
                <td className="py-1 pr-3">{r.action}</td>
                <td className="py-1 pr-3">
                  {r.resource_type} {r.resource_id}
                </td>
                <td className="py-1 text-stone-500">{r.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

function Users() {
  const { t } = useTranslation()
  const { data } = useApi<any[]>('/admin/users')
  return (
    <Card title={t('admin.users')}>
      <ul className="divide-y divide-stone-100 text-sm">
        {data?.map((u) => (
          <li key={u.id} className="flex flex-wrap justify-between gap-2 py-2">
            <span>
              {u.full_name} · {u.phone}
            </span>
            <span className="flex gap-1">
              <Badge>{t(`roles.${u.role}`)}</Badge>
              <Badge tone="blue">{u.language.toUpperCase()}</Badge>
              <Badge tone={u.status === 'ACTIVE' ? 'green' : 'amber'}>{u.status}</Badge>
            </span>
          </li>
        ))}
      </ul>
    </Card>
  )
}

function Sms() {
  const { t } = useTranslation()
  const f = useFormat()
  const { data } = useApi<any[]>('/admin/sms')
  return (
    <Card title={t('admin.smsLog')}>
      <p className="mb-2 text-xs text-stone-500">{t('admin.smsHint')}</p>
      {!data?.length ? (
        <Empty>—</Empty>
      ) : (
        <ul className="divide-y divide-stone-100 text-sm">
          {data.map((m) => (
            <li key={m.id} className="py-2">
              <div className="flex flex-wrap gap-2 text-xs text-stone-500">
                {m.phone} · <Badge tone="blue">{m.language.toUpperCase()}</Badge> · {m.status} · {f.dateTime(m.created_at)}
              </div>
              <div>{m.body}</div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

function TamperDemo() {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const [batchId, setBatchId] = useState('BATCH-1A2B')
  const [msg, setMsg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const run = async (action: 'tamper' | 'restore') => {
    setError(null)
    try {
      const r = await api(`/demo/${action}/${batchId}`, { method: 'POST' })
      setMsg(t(`admin.${action}Done`, { id: r.batch_id, qty: r.quantity_kg }))
    } catch (err) {
      setError(errorText(err))
    }
  }
  return (
    <Card title={`🧪 ${t('admin.tamperTitle')}`}>
      <p className="mb-3 text-sm text-stone-600">{t('admin.tamperExplainer')}</p>
      <div className="flex flex-wrap items-end gap-2">
        <Field label={t('ghala.batch')}>
          <input className="input font-mono" value={batchId} onChange={(e) => setBatchId(e.target.value.trim())} />
        </Field>
        <Button variant="danger" onClick={() => run('tamper')}>
          {t('admin.tamper')}
        </Button>
        <Button variant="secondary" onClick={() => run('restore')}>
          {t('admin.restore')}
        </Button>
        <Link to={`/verify/${batchId}`} className="pb-2 text-sm text-brand-800 underline">
          🔎 {t('ghala.verify')}
        </Link>
      </div>
      {msg && <p className="mt-2 text-sm">{msg}</p>}
      <ErrorNote text={error} />
    </Card>
  )
}
