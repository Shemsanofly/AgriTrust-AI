import { ArrowLeft, Link2, ShieldCheck, Store, Thermometer, Droplets, Clock, Scale } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { ChartLegend, CHART, TimeSeriesChart } from '../../components/Charts'
import { CropImage } from '../../components/crops'
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
  Recommendation,
  RiskBadge,
  RiskScale,
  SimulatedTag,
  Stat,
  StatStrip,
  StatusBadge,
  useToast,
} from '../../components/ui'
import { api } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { useApi, useBi, useErrorText, useFormat } from '../../lib/hooks'
import type { Batch } from '../farmer/shared'
import { QrImage } from './BatchParts'

export function BatchDetailPage({ backTo }: { backTo: string }) {
  const { batchId } = useParams()
  const { t } = useTranslation()
  const bi = useBi()
  const f = useFormat()
  const errorText = useErrorText()
  const { user } = useAuth()
  const { data: batch, loading, error, reload } = useApi<Batch>(`/batches/${batchId}`)
  const { data: history } = useApi<{ ts: string; temperature_c: number; humidity_pct: number }[]>(batch?.warehouse ? `/batches/${batchId}/storage-history?hours=72` : null, [batch?.id])

  if (loading && !batch) return <Loading rows={4} />
  if (error || !batch) return <ErrorState text={errorText(error)} onRetry={reload} />

  const isFarmer = user?.role === 'FARMER'
  const isOperator = user?.role === 'WAREHOUSE_OPERATOR'
  const risk = batch.risk
  const riskTone = risk?.level === 'HIGH' ? 'red' : risk?.level === 'MEDIUM' ? 'amber' : 'green'

  return (
    <div className="space-y-5">
      <Link to={backTo} className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink">
        <ArrowLeft className="size-4" aria-hidden /> {t('common.back')}
      </Link>

      <header className="flex flex-wrap items-center gap-4">
        <CropImage crop={batch.crop_type} className="size-16 shrink-0 sm:size-20" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-[22px] font-semibold tracking-tight">{t(`crops.${batch.crop_type}`)}</h1>
            <StatusBadge status={batch.status} />
            {batch.grade && <Badge tone="gold">{t('ghala.gradeX', { grade: batch.grade })}</Badge>}
          </div>
          <p className="num font-mono text-sm text-muted">{batch.id}</p>
        </div>
        <Link to={`/verify/${batch.id}`} className="inline-flex min-h-11 items-center gap-2 rounded-md border border-line-strong bg-surface px-4 text-sm font-medium hover:bg-sunken">
          <ShieldCheck className="size-4 text-forest-700" aria-hidden /> {t('verify.viewRecord')}
        </Link>
      </header>

      {batch.status === 'HARVESTED' && (
        <Notice tone="info" title={t('ghala.deliverTitle')}>
          {isFarmer ? t('ghala.deliverHint') : t('ghala.deliverOperatorHint')}
        </Notice>
      )}

      <StatStrip>
        <Stat icon={Scale} label={batch.warehouse ? t('ghala.available') : t('ghala.harvested')} value={f.kg(batch.warehouse ? batch.available_kg : batch.quantity_kg)} sub={batch.warehouse ? t('ghala.ofKg', { kg: f.kg(batch.receipt?.quantity_kg) }) : f.date(batch.harvest_date)} />
        <Stat icon={Clock} label={t('ghala.storageDuration')} value={batch.days_in_storage != null ? t('ghala.daysShort', { count: batch.days_in_storage }) : '—'} sub={batch.receipt ? t('ghala.since', { date: f.date(batch.receipt.date_in) }) : t('ghala.notStored')} />
        <Stat icon={Thermometer} label={t('ghala.temperature')} value={risk?.stats?.temp_avg != null ? `${f.num(risk.stats.temp_avg, 1)}°C` : '—'} sub={risk?.stats?.temp_max != null ? t('ghala.max', { v: `${f.num(risk.stats.temp_max, 1)}°C` }) : t('ghala.last24h')} />
        <Stat icon={Droplets} label={t('ghala.humidity')} value={risk?.stats?.rh_avg != null ? `${f.num(risk.stats.rh_avg, 1)}%` : '—'} sub={risk?.stats?.rh_max != null ? t('ghala.max', { v: `${f.num(risk.stats.rh_max, 1)}%` }) : t('ghala.last24h')} tone={risk?.stats?.rh_avg != null && risk.stats.rh_avg >= 75 ? 'red' : undefined} />
      </StatStrip>

      <div className="grid gap-5 lg:grid-cols-[1.4fr_1fr]">
        <div className="space-y-5">
          {risk && risk.level !== 'UNKNOWN' && (
            <Recommendation
              tone={riskTone}
              label={
                <span className="flex items-center gap-2">
                  {t('ghala.spoilageRisk')} <RiskBadge level={risk.level} />
                </span>
              }
              headline={bi(risk.headline)}
              reasons={risk.drivers.map((d) => bi(d))}
              meta={`${t('ghala.riskMeta')} · ${risk.model_version}`}
            >
              <div className="space-y-3">
                <p className="text-sm text-ink-soft">
                  <span className="font-semibold text-ink">{t('ghala.whatToDo')}: </span>
                  {bi(risk.action)}
                </p>
                <div className="max-w-xs">
                  <RiskScale level={risk.level} />
                </div>
              </div>
            </Recommendation>
          )}

          {batch.warehouse && (
            <Card title={t('ghala.conditions72h')} actions={<SimulatedTag label={t('ghala.sensorSimulated')} />}>
              {history?.length ? (
                <div className="space-y-4">
                  <TimeSeriesChart height={170} data={history} series={[{ key: 'humidity_pct', label: t('ghala.humidity'), unit: '%', color: CHART.humidity, limit: 65 }]} />
                  <TimeSeriesChart height={140} data={history} series={[{ key: 'temperature_c', label: t('ghala.temperature'), unit: '°C', color: CHART.temperature, limit: 27 }]} />
                  <ChartLegend
                    items={[
                      { label: t('ghala.humidity'), color: CHART.humidity },
                      { label: t('ghala.temperature'), color: CHART.temperature },
                      { label: t('ghala.safeLimit'), color: '#5e6a5f', dashed: true },
                    ]}
                  />
                </div>
              ) : (
                <EmptyState compact title={t('farm.noReadings')} />
              )}
            </Card>
          )}

          {!!batch.storage_records?.length && (
            <Card title={t('ghala.anchoredSummaries')} subtitle={t('ghala.anchoredSummariesSub')}>
              <ul className="-my-2 divide-y divide-line text-sm">
                {batch.storage_records.map((r) => (
                  <li key={r.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 py-2.5">
                    <span className="min-w-0 flex-1 text-ink-soft">
                      {f.dateTime(r.window_start)} – {f.dateTime(r.window_end)}
                    </span>
                    <span className="num text-muted">
                      {f.num(r.temp_avg, 1)}°C · {f.num(r.rh_avg, 1)}%
                    </span>
                    <RiskBadge level={r.risk_level} />
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>

        <div className="space-y-5">
          {isFarmer && batch.status === 'IN_STORAGE' && <ListingCard batch={batch} onChanged={reload} />}
          {isOperator && batch.status === 'IN_STORAGE' && <AnchorCard batchId={batch.id} onDone={reload} />}

          <Card title={t('ghala.receipt')}>
            {batch.receipt ? (
              <>
                <KeyValues
                  items={[
                    [t('ghala.receiptNo'), <span className="num font-mono">{batch.receipt.id}</span>],
                    [t('ghala.warehouse'), batch.warehouse?.name],
                    [t('ghala.weighedIn'), f.kg(batch.receipt.quantity_kg)],
                    [t('ghala.released'), f.kg(batch.receipt.released_kg)],
                    [t('ghala.bay'), batch.receipt.bay || '—'],
                    [t('ghala.receiptStatus'), <StatusBadge status={batch.receipt.status} />],
                  ]}
                />
                <p className="mt-3 text-xs text-muted">{t('ghala.receiptLegal')}</p>
              </>
            ) : (
              <EmptyState compact title={t('ghala.noReceipt')} body={t('ghala.noReceiptBody')} />
            )}
          </Card>

          <Card title={t('verify.trustTitle')}>
            <div className="flex items-center gap-4">
              <QrImage id={batch.id} />
              <div className="min-w-0 text-sm">
                <p className="text-ink-soft">{t('verify.trustBody')}</p>
                <ul className="mt-2 space-y-1 text-xs text-muted">
                  {batch.proofs?.map((p) => (
                    <li key={`${p.entity_type}-${p.entity_id}`} className="flex items-center gap-1.5">
                      <Link2 className="size-3.5" aria-hidden />
                      {t(`verify.types.${p.entity_type}`)} · <span className="num font-mono">{p.tx_hash.slice(0, 10)}…</span>
                      {p.mode === 'SIMULATED' && <SimulatedTag label={t('verify.localLedger')} />}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}

function ListingCard({ batch, onChanged }: { batch: Batch; onChanged: () => void }) {
  const { t } = useTranslation()
  const f = useFormat()
  const toast = useToast()
  const errorText = useErrorText()
  const [price, setPrice] = useState(String(batch.price_per_kg ?? ''))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const priceNum = Number(price.replace(/[, ]/g, ''))

  const save = async (listed: boolean, e?: FormEvent) => {
    e?.preventDefault()
    if (listed && !(priceNum > 0)) return setError(t('validation.price'))
    setBusy(true)
    setError(null)
    try {
      await api(`/batches/${batch.id}/listing`, { method: 'PATCH', body: { listed, price_per_kg: listed ? priceNum : null } })
      toast(listed ? t('ghala.listedToast') : t('ghala.unlistedToast'))
      onChanged()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card title={t('ghala.sellTitle')} subtitle={batch.listed ? t('ghala.sellingNow') : t('ghala.sellSubtitle')} actions={batch.listed && <Badge tone="green" icon={Store}>{t('ghala.listed')}</Badge>}>
      <form onSubmit={(e) => save(true, e)} className="space-y-3">
        <Field label={t('ghala.pricePerKg')} hint={priceNum > 0 ? t('ghala.worth', { total: f.tzs(priceNum * batch.available_kg) }) : t('ghala.priceHint')}>
          <input className="input num" inputMode="numeric" value={price} onChange={(e) => setPrice(e.target.value)} placeholder="780" />
        </Field>
        <ErrorNote text={error} />
        <div className="flex flex-wrap gap-2">
          <Button type="submit" busy={busy} icon={Store}>
            {batch.listed ? t('ghala.updatePrice') : t('ghala.listForSale')}
          </Button>
          {batch.listed && (
            <Button variant="secondary" disabled={busy} onClick={() => save(false)}>
              {t('ghala.unlist')}
            </Button>
          )}
        </div>
      </form>
    </Card>
  )
}

function AnchorCard({ batchId, onDone }: { batchId: string; onDone: () => void }) {
  const { t } = useTranslation()
  const toast = useToast()
  const errorText = useErrorText()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const run = async () => {
    setBusy(true)
    setError(null)
    try {
      await api(`/batches/${batchId}/storage-records`, { method: 'POST' })
      toast(t('ghala.anchored'))
      onDone()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }
  return (
    <Card title={t('ghala.anchorTitle')} subtitle={t('ghala.anchorSubtitle')}>
      <Button variant="secondary" icon={Link2} busy={busy} onClick={run}>
        {t('ghala.anchorWindow')}
      </Button>
      <div className="mt-2">
        <ErrorNote text={error} />
      </div>
    </Card>
  )
}
