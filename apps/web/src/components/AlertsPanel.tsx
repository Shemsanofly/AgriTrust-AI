import { useTranslation } from 'react-i18next'
import { api } from '../lib/api'
import { useApi, useBi, useFormat, type Bi } from '../lib/hooks'
import { Button, Card, Empty } from './ui'

type Alert = { id: number; kind: string; severity: string; message: Bi; created_at: string; read: boolean; resolved_at: string | null }

const ICON: Record<string, string> = {
  DRY_SOIL: '🌵',
  HEAT: '🌡️',
  SPOILAGE_RISK: '🍂',
  SENSOR_SUSPECT: '📡',
  ORDER: '🧺',
  SALE: '✅',
  RECEIPT: '🧾',
  LOAN: '💰',
  CLAIM: '🛡️',
  INSURANCE: '🛡️',
  CONSENT: '🤝',
  SECURITY: '🔒',
  FRAUD: '🚩',
  CONTEST: '✋',
}

export function AlertsPanel({ refreshKey = 0, limit = 6 }: { refreshKey?: number; limit?: number }) {
  const { t } = useTranslation()
  const bi = useBi()
  const f = useFormat()
  const { data, reload } = useApi<Alert[]>('/alerts', [refreshKey])
  const open = (data ?? []).filter((a) => !a.resolved_at).slice(0, limit)

  const resolve = async (id: number) => {
    await api(`/alerts/${id}/resolve`, { method: 'POST' })
    reload()
  }

  return (
    <Card title={`🔔 ${t('alerts.title')}`}>
      {open.length === 0 ? (
        <Empty>{t('alerts.none')}</Empty>
      ) : (
        <ul className="space-y-2">
          {open.map((a) => (
            <li
              key={a.id}
              className={`flex items-start gap-3 rounded-xl p-3 text-sm ${a.severity === 'CRITICAL' ? 'bg-red-50' : a.severity === 'WARNING' ? 'bg-amber-50' : 'bg-stone-50'}`}
            >
              <span className="text-lg" aria-hidden>
                {ICON[a.kind] ?? '•'}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-stone-900">{bi(a.message)}</p>
                <p className="mt-0.5 text-xs text-stone-500">{f.dateTime(a.created_at)}</p>
              </div>
              <Button variant="ghost" className="min-h-8 px-2 text-xs" onClick={() => resolve(a.id)}>
                {t('alerts.resolve')}
              </Button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
