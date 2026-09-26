import {
  Bell,
  CheckCircle2,
  CloudRain,
  Flag,
  HandCoins,
  Handshake,
  Radio,
  Receipt,
  ShieldAlert,
  ShoppingBasket,
  Thermometer,
  Umbrella,
  Warehouse,
  Droplets,
  type LucideIcon,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { api } from '../lib/api'
import { useApi, useBi, useFormat, type Bi } from '../lib/hooks'
import { Button, Card, EmptyState, Skeleton, cx } from './ui'

export type Alert = { id: number; kind: string; severity: string; message: Bi; created_at: string; read: boolean; resolved_at: string | null; entity_type?: string; entity_id?: string }

export const ALERT_ICON: Record<string, LucideIcon> = {
  DRY_SOIL: Droplets,
  HEAT: Thermometer,
  SPOILAGE_RISK: Warehouse,
  SENSOR_SUSPECT: Radio,
  ORDER: ShoppingBasket,
  SALE: CheckCircle2,
  RECEIPT: Receipt,
  LOAN: HandCoins,
  CLAIM: Umbrella,
  INSURANCE: Umbrella,
  CONSENT: Handshake,
  SECURITY: ShieldAlert,
  FRAUD: Flag,
  CONTEST: Flag,
  RAIN: CloudRain,
}

export function AlertRow({ alert, onResolve }: { alert: Alert; onResolve?: (id: number) => void }) {
  const { t } = useTranslation()
  const bi = useBi()
  const f = useFormat()
  const Icon = ALERT_ICON[alert.kind] ?? Bell
  const tone = alert.severity === 'CRITICAL' ? 'text-danger-700 bg-danger-100' : alert.severity === 'WARNING' ? 'text-warn-700 bg-warn-100' : 'text-ink-soft bg-sunken'
  return (
    <li className="flex items-start gap-3 py-3">
      <span className={cx('mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-md', tone)}>
        <Icon className="size-4" aria-hidden />
      </span>
      <div className="min-w-0 flex-1">
        <p className={cx('text-sm', alert.resolved_at ? 'text-muted' : 'text-ink')}>{bi(alert.message)}</p>
        <p className="mt-0.5 text-xs text-muted">
          {f.relative(alert.created_at)}
          {alert.severity !== 'INFO' && !alert.resolved_at && <> · {t(`alerts.severity.${alert.severity}`)}</>}
          {alert.resolved_at && <> · {t('alerts.handled')}</>}
        </p>
      </div>
      {onResolve && !alert.resolved_at && (
        <Button variant="ghost" size="sm" onClick={() => onResolve(alert.id)}>
          {t('alerts.resolve')}
        </Button>
      )}
    </li>
  )
}

/** Compact list of open alerts for dashboards. */
export function AlertsPanel({ refreshKey = 0, limit = 5, title }: { refreshKey?: number; limit?: number; title?: string }) {
  const { t } = useTranslation()
  const { data, loading, reload } = useApi<Alert[]>('/alerts', [refreshKey])
  const open = (data ?? []).filter((a) => !a.resolved_at)

  const resolve = async (id: number) => {
    await api(`/alerts/${id}/resolve`, { method: 'POST' })
    reload()
  }

  return (
    <Card title={title ?? t('alerts.title')} actions={open.length > 0 && <span className="text-xs text-muted">{t('alerts.openCount', { count: open.length })}</span>}>
      {loading && !data ? (
        <div className="space-y-2">
          <Skeleton className="h-10" />
          <Skeleton className="h-10" />
        </div>
      ) : open.length === 0 ? (
        <EmptyState compact icon={CheckCircle2} title={t('alerts.none')} body={t('alerts.noneBody')} />
      ) : (
        <ul className="-my-3 divide-y divide-line">
          {open.slice(0, limit).map((a) => (
            <AlertRow key={a.id} alert={a} onResolve={resolve} />
          ))}
        </ul>
      )}
    </Card>
  )
}
