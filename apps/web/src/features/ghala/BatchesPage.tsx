import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { AlertsPanel } from '../../components/AlertsPanel'
import { TimeSeriesChart } from '../../components/Charts'
import { Badge, Button, Card, Empty, ErrorNote, Field, Loading, RiskBadge, SimulatedTag, StatusBadge } from '../../components/ui'
import { api, apiUrl } from '../../lib/api'
import { useApi, useBi, useErrorText, useFormat, type Bi } from '../../lib/hooks'

export type Batch = {
  id: string
  crop_type: string
  harvest_date: string
  quantity_kg: number
  available_kg: number
  grade: string | null
  status: string
  listed: boolean
  price_per_kg: number | null
  qr_url: string
  warehouse: { id: number; name: string; region: string } | null
  receipt: { id: string; status: string; quantity_kg: number; released_kg: number; grade: string; date_in: string; bay: string } | null
  risk: { level: string; drivers: Bi[]; action: Bi; model_version: string } | null
}

export function BatchesPage() {
  const { t } = useTranslation()
  const { data: batches, loading, reload } = useApi<Batch[]>('/batches')
  const { data: farms } = useApi<any[]>('/farms')
  const readyCrops = (farms ?? []).flatMap((farm) =>
    farm.crops.filter((c: any) => c.growth_stage === 'maturity').map((c: any) => ({ ...c, farm_name: farm.name })),
  )

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">🏚️ {t('ghala.farmerTitle')}</h1>
      <HarvestForm crops={readyCrops} onDone={reload} />
      {loading && !batches ? <Loading /> : !batches?.length ? <Empty>{t('ghala.noBatches')}</Empty> : batches.map((b) => <BatchCard key={b.id} batch={b} onChanged={reload} />)}
      <AlertsPanel />
    </div>
  )
}

function HarvestForm({ crops, onDone }: { crops: any[]; onDone: () => void }) {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const [cropId, setCropId] = useState('')
  const [qty, setQty] = useState('')
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  if (!crops.length) return null

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api('/harvests', { method: 'POST', body: { crop_id: Number(cropId || crops[0].id), quantity_kg: Number(qty), harvest_date: date } })
      setQty('')
      onDone()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card title={`🌾 ${t('ghala.recordHarvest')}`}>
      <form onSubmit={submit} className="grid gap-3 sm:grid-cols-4 sm:items-end">
        <Field label={t('farm.crop')}>
          <select className="input" value={cropId} onChange={(e) => setCropId(e.target.value)}>
            {crops.map((c) => (
              <option key={c.id} value={c.id}>
                {t(`crops.${c.crop_type}`)} · {c.farm_name}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t('ghala.quantityKg')}>
          <input className="input" inputMode="decimal" value={qty} onChange={(e) => setQty(e.target.value)} required />
        </Field>
        <Field label={t('ghala.harvestDate')}>
          <input className="input" type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
        </Field>
        <Button type="submit" busy={busy}>
          {t('ghala.createBatch')}
        </Button>
      </form>
      <ErrorNote text={error} />
      <p className="mt-2 text-xs text-stone-500">{t('ghala.batchHint')}</p>
    </Card>
  )
}

export function BatchCard({ batch, onChanged, operator = false }: { batch: Batch; onChanged: () => void; operator?: boolean }) {
  const { t } = useTranslation()
  const bi = useBi()
  const f = useFormat()
  const errorText = useErrorText()
  const [open, setOpen] = useState(false)
  const [price, setPrice] = useState(String(batch.price_per_kg ?? ''))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { data: history } = useApi<any[]>(open && batch.warehouse ? `/batches/${batch.id}/storage-history?hours=72` : null)

  const setListing = async (listed: boolean) => {
    setBusy(true)
    setError(null)
    try {
      await api(`/batches/${batch.id}/listing`, { method: 'PATCH', body: { listed, price_per_kg: price ? Number(price) : null } })
      onChanged()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  const anchorWindow = async () => {
    setBusy(true)
    setError(null)
    try {
      await api(`/batches/${batch.id}/storage-records`, { method: 'POST' })
      onChanged()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <div className="flex gap-4">
        <img src={apiUrl(`/qr/${batch.id}.svg`)} alt={`QR ${batch.id}`} className="h-20 w-20 shrink-0 rounded-lg border border-stone-200" loading="lazy" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono font-semibold">{batch.id}</span>
            <StatusBadge status={batch.status} />
            {batch.grade && <Badge tone="purple">{t('ghala.grade')} {batch.grade}</Badge>}
            {batch.listed && <Badge tone="green">🧺 {t('ghala.listed')}</Badge>}
          </div>
          <p className="mt-1 text-sm text-stone-700">
            {t(`crops.${batch.crop_type}`)} · {f.num(batch.quantity_kg)} kg · {t('ghala.harvested')} {f.date(batch.harvest_date)}
          </p>
          {batch.warehouse && (
            <p className="text-sm text-stone-600">
              🏚️ {batch.warehouse.name} · {t('ghala.available')}: <b>{f.num(batch.available_kg)} kg</b>
            </p>
          )}
          <div className="mt-1 flex flex-wrap gap-3 text-sm">
            <Link to={`/verify/${batch.id}`} className="text-brand-800 underline">
              🔎 {t('ghala.verify')}
            </Link>
            {batch.receipt && (
              <Link to={`/verify/${batch.receipt.id}`} className="text-brand-800 underline">
                🧾 {batch.receipt.id}
              </Link>
            )}
            {batch.warehouse && (
              <button className="text-brand-800 underline" onClick={() => setOpen((v) => !v)}>
                📈 {open ? t('common.hide') : t('ghala.conditions')}
              </button>
            )}
          </div>
        </div>
      </div>

      {batch.risk && batch.risk.level !== 'UNKNOWN' && (
        <div className={`mt-3 rounded-xl p-3 text-sm ${batch.risk.level === 'HIGH' ? 'bg-red-50' : batch.risk.level === 'MEDIUM' ? 'bg-amber-50' : 'bg-green-50'}`}>
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium">{t('ghala.spoilageRisk')}:</span> <RiskBadge level={batch.risk.level} />
            <Badge tone="blue">{t('farm.rulesModel')}</Badge>
          </div>
          <ul className="mt-1 list-disc pl-5 text-stone-700">
            {batch.risk.drivers.map((d, i) => (
              <li key={i}>{bi(d)}</li>
            ))}
          </ul>
          <p className="mt-1 font-medium">👉 {bi(batch.risk.action)}</p>
        </div>
      )}

      {open && (
        <div className="mt-3">
          <div className="mb-1 flex items-center gap-2 text-sm text-stone-600">
            {t('ghala.last72h')} <SimulatedTag />
          </div>
          {history?.length ? (
            <TimeSeriesChart
              data={history}
              height={200}
              series={[
                { key: 'humidity_pct', label: t('ghala.humidity'), unit: '%', color: '#0369a1', limit: 65 },
                { key: 'temperature_c', label: t('ghala.temperature'), unit: '°C', color: '#c2410c', limit: 27 },
              ]}
            />
          ) : (
            <Empty>{t('farm.noReadings')}</Empty>
          )}
        </div>
      )}

      {!operator && batch.status === 'IN_STORAGE' && (
        <div className="mt-3 flex flex-wrap items-end gap-2 border-t border-stone-100 pt-3">
          <Field label={t('ghala.pricePerKg')}>
            <input className="input w-36" inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} />
          </Field>
          {batch.listed ? (
            <>
              <Button variant="secondary" busy={busy} onClick={() => setListing(true)}>
                {t('ghala.updatePrice')}
              </Button>
              <Button variant="ghost" busy={busy} onClick={() => setListing(false)}>
                {t('ghala.unlist')}
              </Button>
            </>
          ) : (
            <Button busy={busy} onClick={() => setListing(true)} disabled={!price}>
              🧺 {t('ghala.listForSale')}
            </Button>
          )}
        </div>
      )}
      {!operator && batch.status === 'HARVESTED' && <p className="mt-3 text-sm text-stone-600">ℹ️ {t('ghala.deliverHint')}</p>}
      {operator && batch.status === 'IN_STORAGE' && (
        <div className="mt-3 border-t border-stone-100 pt-3">
          <Button variant="secondary" busy={busy} onClick={anchorWindow}>
            🔗 {t('ghala.anchorWindow')}
          </Button>
        </div>
      )}
      <ErrorNote text={error} />
    </Card>
  )
}
