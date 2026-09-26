import { ChevronRight, QrCode } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { CropImage } from '../../components/crops'
import { Badge, RiskBadge, StatusBadge } from '../../components/ui'
import { apiUrl } from '../../lib/api'
import { useFormat } from '../../lib/hooks'
import type { Batch } from '../farmer/shared'

export function QrImage({ id, size = 'md' }: { id: string; size?: 'sm' | 'md' | 'lg' }) {
  const { t } = useTranslation()
  const px = { sm: 'size-16', md: 'size-24', lg: 'size-40' }[size]
  return <img src={apiUrl(`/qr/${id}.svg`)} alt={t('verify.qrAlt', { id })} className={`${px} rounded border border-line bg-white p-1`} loading="lazy" />
}

/** One row per batch: used by farmers (their batches) and warehouse operators (stock). */
export function BatchRow({ batch, to, showOwner }: { batch: Batch & { owner?: string }; to: string; showOwner?: boolean }) {
  const { t } = useTranslation()
  const f = useFormat()
  return (
    <li>
      <Link to={to} className="flex items-center gap-3 px-4 py-3 hover:bg-sunken/60 sm:px-5">
        <CropImage crop={batch.crop_type} className="size-12 shrink-0" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="font-medium">{t(`crops.${batch.crop_type}`)}</span>
            <span className="num font-mono text-xs text-muted">{batch.id}</span>
            {batch.grade && <Badge tone="gold">{t('ghala.gradeX', { grade: batch.grade })}</Badge>}
          </div>
          <div className="num mt-0.5 text-[13px] text-muted">
            {batch.warehouse ? (
              <>
                {f.kg(batch.available_kg)} · {batch.warehouse.name} · {t('ghala.daysStored', { count: batch.days_in_storage ?? 0 })}
              </>
            ) : (
              <>
                {f.kg(batch.quantity_kg)} · {t('ghala.harvestedOn', { date: f.date(batch.harvest_date) })}
              </>
            )}
            {showOwner && batch.owner && <> · {batch.owner}</>}
          </div>
        </div>
        <div className="hidden flex-col items-end gap-1 sm:flex">
          <StatusBadge status={batch.status} />
          {batch.listed && <Badge tone="green">{t('ghala.listed')}</Badge>}
        </div>
        {batch.risk && batch.risk.level !== 'UNKNOWN' ? <RiskBadge level={batch.risk.level} /> : <QrCode className="size-4 text-muted sm:hidden" aria-hidden />}
        <ChevronRight className="size-4 shrink-0 text-muted" aria-hidden />
      </Link>
    </li>
  )
}
