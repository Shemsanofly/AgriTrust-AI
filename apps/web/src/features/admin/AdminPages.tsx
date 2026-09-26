import { Flag, Link2, MessageSquareText, ScrollText, ShieldCheck, Users } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { AlertRow, type Alert } from '../../components/AlertsPanel'
import { Badge, Button, Card, EmptyState, ErrorNote, Field, Loading, Notice, PageHeader, Stat, StatStrip, useToast } from '../../components/ui'
import { api } from '../../lib/api'
import { useApi, useErrorText, useFormat } from '../../lib/hooks'

type AuditRow = { id: number; ts: string; actor_name: string | null; actor_role: string | null; action: string; resource_type: string; resource_id: string | null; reason: string | null }
type UserRow = { id: number; phone: string; full_name: string; role: string; language: string; status: string }

export function AdminOverview() {
  const { t } = useTranslation()
  const f = useFormat()
  const { data: users } = useApi<UserRow[]>('/admin/users')
  const { data: alerts } = useApi<Alert[]>('/admin/alerts')
  const { data: audit } = useApi<AuditRow[]>('/admin/audit?limit=8')
  const { data: ledger } = useApi<{ mode: string; simulated_ledger_intact: boolean | null }>('/admin/ledger')
  const openAlerts = (alerts ?? []).filter((a) => !a.resolved_at)
  return (
    <div className="space-y-5">
      <PageHeader title={t('admin.title')} subtitle={t('admin.subtitle')} />
      <StatStrip>
        <Stat icon={Users} label={t('admin.users')} value={users?.length ?? '—'} sub={users ? t('admin.farmersCount', { count: users.filter((u) => u.role === 'FARMER').length }) : undefined} />
        <Stat icon={Flag} label={t('admin.openAlerts')} value={openAlerts.length} tone={openAlerts.length ? 'amber' : undefined} />
        <Stat icon={Link2} label={t('admin.trustLayer')} value={ledger ? (ledger.mode === 'ONCHAIN' ? t('verify.onchain') : t('verify.localLedger')) : '—'} sub={ledger?.simulated_ledger_intact == null ? undefined : ledger.simulated_ledger_intact ? t('admin.ledgerIntact') : t('admin.ledgerBroken')} tone={ledger?.simulated_ledger_intact === false ? 'red' : undefined} />
        <Stat icon={ScrollText} label={t('admin.auditEntries')} value={audit ? `${audit.length}+` : '—'} sub={t('admin.appendOnly')} />
      </StatStrip>
      <div className="grid gap-5 lg:grid-cols-2">
        <Card title={t('admin.fraudAlerts')} actions={<Link to="/fraud" className="text-sm font-medium text-forest-800">{t('common.viewAll')}</Link>}>
          {!openAlerts.length ? <EmptyState compact icon={ShieldCheck} title={t('alerts.none')} /> : <ul className="-my-3 divide-y divide-line">{openAlerts.slice(0, 4).map((a) => <AlertRow key={a.id} alert={a} />)}</ul>}
        </Card>
        <Card title={t('admin.recentAudit')} actions={<Link to="/audit" className="text-sm font-medium text-forest-800">{t('common.viewAll')}</Link>}>
          <ul className="-my-2 divide-y divide-line text-sm">
            {audit?.map((r) => (
              <li key={r.id} className="py-2">
                <span className="font-medium">{r.actor_name ?? '—'}</span> <span className="text-muted">· {r.action} {r.resource_type}</span>
                <div className="text-xs text-muted">{f.relative(r.ts)}</div>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  )
}

export function FraudPage() {
  const { t } = useTranslation()
  const { data, loading, reload } = useApi<Alert[]>('/admin/alerts')
  const resolve = async (id: number) => {
    await api(`/alerts/${id}/resolve`, { method: 'POST' })
    reload()
  }
  return (
    <div>
      <PageHeader title={t('admin.fraudAlerts')} subtitle={t('admin.fraudSubtitle')} />
      <Card>
        {loading && !data ? <Loading /> : !data?.length ? <EmptyState icon={ShieldCheck} title={t('alerts.none')} /> : <ul className="-my-3 divide-y divide-line">{data.map((a) => <AlertRow key={a.id} alert={a} onResolve={resolve} />)}</ul>}
      </Card>
    </div>
  )
}

export function AuditPage() {
  const { t } = useTranslation()
  const f = useFormat()
  const { data, loading } = useApi<AuditRow[]>('/admin/audit')
  const [q, setQ] = useState('')
  const rows = (data ?? []).filter((r) => !q || JSON.stringify(r).toLowerCase().includes(q.toLowerCase()))
  return (
    <div>
      <PageHeader title={t('admin.auditLog')} subtitle={t('admin.auditSubtitle')} />
      <input className="input mb-4 max-w-sm" type="search" placeholder={t('admin.searchAudit')} value={q} onChange={(e) => setQ(e.target.value)} aria-label={t('admin.searchAudit')} />
      <Card padded={false}>
        {loading && !data ? (
          <div className="p-4">
            <Loading />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[44rem] text-left text-sm">
              <thead className="bg-sunken text-xs text-muted">
                <tr>
                  <th className="px-5 py-2.5 font-medium">{t('admin.when')}</th>
                  <th className="px-3 py-2.5 font-medium">{t('admin.who')}</th>
                  <th className="px-3 py-2.5 font-medium">{t('admin.action')}</th>
                  <th className="px-3 py-2.5 font-medium">{t('admin.resource')}</th>
                  <th className="px-5 py-2.5 font-medium">{t('admin.why')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td className="num px-5 py-2.5 whitespace-nowrap text-muted">{f.dateTime(r.ts)}</td>
                    <td className="px-3 py-2.5">
                      {r.actor_name ?? '—'} {r.actor_role && <span className="text-xs text-muted">· {t(`roles.${r.actor_role}`)}</span>}
                    </td>
                    <td className="px-3 py-2.5 font-mono text-xs">{r.action}</td>
                    <td className="px-3 py-2.5 text-xs">
                      {r.resource_type} <span className="num font-mono text-muted">{r.resource_id}</span>
                    </td>
                    <td className="px-5 py-2.5 text-xs text-muted">{r.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}

export function UsersPage() {
  const { t } = useTranslation()
  const { data, loading } = useApi<UserRow[]>('/admin/users')
  return (
    <div>
      <PageHeader title={t('admin.users')} subtitle={t('admin.usersSubtitle')} />
      <Card padded={false}>
        {loading && !data ? (
          <div className="p-4">
            <Loading />
          </div>
        ) : (
          <ul className="divide-y divide-line">
            {data?.map((u) => (
              <li key={u.id} className="flex flex-wrap items-center gap-3 px-4 py-3 text-sm sm:px-5">
                <div className="min-w-0 flex-1">
                  <div className="font-medium">{u.full_name}</div>
                  <div className="num text-xs text-muted">{u.phone}</div>
                </div>
                <Badge>{t(`roles.${u.role}`)}</Badge>
                <Badge tone="blue">{u.language === 'sw' ? 'Kiswahili' : 'English'}</Badge>
                <Badge tone={u.status === 'ACTIVE' ? 'green' : 'amber'}>{t(`admin.userStatus.${u.status}`, { defaultValue: u.status })}</Badge>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}

export function SmsPage() {
  const { t } = useTranslation()
  const f = useFormat()
  const { data, loading } = useApi<{ id: number; phone: string; language: string; body: string; status: string; created_at: string }[]>('/admin/sms')
  return (
    <div>
      <PageHeader title={t('admin.smsLog')} subtitle={t('admin.smsHint')} />
      <Card padded={false}>
        {loading && !data ? (
          <div className="p-4">
            <Loading />
          </div>
        ) : !data?.length ? (
          <EmptyState icon={MessageSquareText} title={t('admin.noSms')} />
        ) : (
          <ul className="divide-y divide-line">
            {data.map((m) => (
              <li key={m.id} className="px-4 py-3 sm:px-5">
                <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
                  <span className="num">{m.phone}</span>
                  <Badge tone="blue">{m.language.toUpperCase()}</Badge>
                  <Badge tone={m.status === 'SENT' ? 'green' : m.status === 'FAILED' ? 'red' : 'stone'}>{t(`admin.smsStatus.${m.status}`)}</Badge>
                  <span>{f.relative(m.created_at)}</span>
                </div>
                <p className="mt-1 text-sm">{m.body}</p>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}

export function DemoToolsPage() {
  const { t } = useTranslation()
  const toast = useToast()
  const errorText = useErrorText()
  const [batchId, setBatchId] = useState('BATCH-1A2B')
  const [error, setError] = useState<string | null>(null)
  const run = async (action: 'tamper' | 'restore') => {
    setError(null)
    try {
      const r = await api(`/demo/${action}/${batchId.trim()}`, { method: 'POST' })
      toast(t(`admin.${action}Done`, { id: r.batch_id, qty: r.quantity_kg }), action === 'tamper' ? 'warning' : 'success')
    } catch (err) {
      setError(errorText(err))
    }
  }
  return (
    <div className="space-y-5">
      <PageHeader title={t('nav.demoTools')} subtitle={t('admin.demoSubtitle')} />
      <Notice tone="warning">{t('admin.demoWarning')}</Notice>
      <Card title={t('admin.tamperTitle')} subtitle={t('admin.tamperExplainer')}>
        <div className="flex flex-wrap items-end gap-2">
          <Field label={t('ghala.batch')}>
            <input className="input num w-48 font-mono" value={batchId} onChange={(e) => setBatchId(e.target.value.toUpperCase())} />
          </Field>
          <Button variant="danger" onClick={() => run('tamper')}>
            {t('admin.tamper')}
          </Button>
          <Button variant="secondary" onClick={() => run('restore')}>
            {t('admin.restore')}
          </Button>
          <Link to={`/verify/${batchId.trim()}`} className="inline-flex min-h-11 items-center px-2 text-sm font-medium text-forest-800">
            {t('verify.viewRecord')}
          </Link>
        </div>
        <div className="mt-3">
          <ErrorNote text={error} />
        </div>
      </Card>
    </div>
  )
}
