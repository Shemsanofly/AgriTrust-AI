import { ArrowRight, CheckCircle2, Plus, Warehouse, Wheat } from 'lucide-react'
import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'
import { Button, Card, Dialog, EmptyState, ErrorNote, ErrorState, Field, Loading, Notice, PageHeader, Stat, StatStrip } from '../../components/ui'
import { api } from '../../lib/api'
import { useApi, useErrorText, useFormat } from '../../lib/hooks'
import type { Batch, Farm } from '../farmer/shared'
import { BatchRow, QrImage } from './BatchParts'

export function FarmerGhalaPage() {
  const { t } = useTranslation()
  const f = useFormat()
  const errorText = useErrorText()
  const [params, setParams] = useSearchParams()
  const { data: batches, loading, error, reload } = useApi<Batch[]>('/batches')
  const { data: farms, reload: reloadFarms } = useApi<Farm[]>('/farms')
  const [harvestOpen, setHarvestOpen] = useState(params.get('harvest') === '1')

  useEffect(() => {
    if (params.get('harvest') === '1') setHarvestOpen(true)
  }, [params])

  const ready = useMemo(
    () => (farms ?? []).flatMap((farm) => farm.crops.filter((c) => c.growth_stage === 'maturity').map((c) => ({ ...c, farm_name: farm.name }))),
    [farms],
  )
  const stored = (batches ?? []).filter((b) => b.status === 'IN_STORAGE')
  const waiting = (batches ?? []).filter((b) => b.status === 'HARVESTED')
  const past = (batches ?? []).filter((b) => b.status === 'SOLD_OUT')
  const atRisk = stored.filter((b) => b.risk?.level === 'HIGH').length

  const close = () => {
    setHarvestOpen(false)
    if (params.get('harvest')) setParams({}, { replace: true })
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title={t('ghala.farmerTitle')}
        subtitle={t('ghala.farmerSubtitle')}
        actions={
          <Button icon={Plus} onClick={() => setHarvestOpen(true)}>
            {t('ghala.recordHarvest')}
          </Button>
        }
      />

      {loading && !batches ? (
        <Loading rows={3} />
      ) : error ? (
        <ErrorState text={errorText(error)} onRetry={reload} />
      ) : (
        <>
          <StatStrip cols={3}>
            <Stat label={t('ghala.inStorage')} value={f.kg(stored.reduce((s, b) => s + b.available_kg, 0))} sub={t('ghala.batchCount', { count: stored.length })} />
            <Stat label={t('ghala.atRisk')} value={atRisk} tone={atRisk ? 'red' : undefined} sub={atRisk ? t('ghala.actToday') : t('ghala.allSafe')} />
            <Stat label={t('ghala.forSale')} value={f.kg(stored.filter((b) => b.listed).reduce((s, b) => s + b.available_kg, 0))} sub={t('ghala.inMarketplace')} />
          </StatStrip>

          {ready.length > 0 && (
            <Notice tone="info" title={t('ghala.readyTitle', { crop: t(`crops.${ready[0].crop_type}`), farm: ready[0].farm_name })} action={<Button size="sm" onClick={() => setHarvestOpen(true)}>{t('ghala.recordHarvest')}</Button>}>
              {t('ghala.readyBody')}
            </Notice>
          )}

          {waiting.length > 0 && (
            <Card title={t('ghala.waitingTitle')} subtitle={t('ghala.waitingSubtitle')} padded={false}>
              <ul className="divide-y divide-line">
                {waiting.map((b) => (
                  <BatchRow key={b.id} batch={b} to={`/ghala/${b.id}`} />
                ))}
              </ul>
            </Card>
          )}

          <Card title={t('ghala.storedTitle')} padded={false}>
            {stored.length ? (
              <ul className="divide-y divide-line">
                {stored.map((b) => (
                  <BatchRow key={b.id} batch={b} to={`/ghala/${b.id}`} />
                ))}
              </ul>
            ) : (
              <EmptyState icon={Warehouse} title={t('ghala.nothingStored')} body={t('ghala.nothingStoredBody')} />
            )}
          </Card>

          {past.length > 0 && (
            <Card title={t('ghala.soldTitle')} padded={false}>
              <ul className="divide-y divide-line">
                {past.map((b) => (
                  <BatchRow key={b.id} batch={b} to={`/ghala/${b.id}`} />
                ))}
              </ul>
            </Card>
          )}
        </>
      )}

      <HarvestDialog
        open={harvestOpen}
        crops={ready}
        onClose={close}
        onCreated={() => {
          reload()
          reloadFarms()
        }}
      />
    </div>
  )
}

type ReadyCrop = { id: number; crop_type: string; farm_name: string; variety?: string }

/** Harvest → batch + QR + on-chain proof, then point the farmer to a verified ghala. */
function HarvestDialog({ open, crops, onClose, onCreated }: { open: boolean; crops: ReadyCrop[]; onClose: () => void; onCreated: () => void }) {
  const { t } = useTranslation()
  const f = useFormat()
  const errorText = useErrorText()
  const { data: warehouses } = useApi<{ id: number; name: string; region: string; verified: boolean }[]>(open ? '/warehouses' : null)
  const verifiedWarehouses = warehouses?.filter((w) => w.verified) ?? []
  const [cropId, setCropId] = useState('')
  const [warehouseId, setWarehouseId] = useState('')
  const [qty, setQty] = useState('')
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [created, setCreated] = useState<Batch | null>(null)

  useEffect(() => {
    if (open) {
      setCreated(null)
      setError(null)
      setQty('')
    }
  }, [open])

  useEffect(() => {
    if (!warehouseId && verifiedWarehouses.length) setWarehouseId(String(verifiedWarehouses[0].id))
  }, [verifiedWarehouses, warehouseId])

  const qtyNum = Number(qty.replace(',', '.'))
  const qtyError = qty && !(qtyNum > 0) ? t('validation.quantity') : null

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!(qtyNum > 0)) return setError(t('validation.quantity'))
    if (!warehouseId) return setError(t('validation.required'))
    setBusy(true)
    setError(null)
    try {
      const batch = await api<Batch>('/harvests', { method: 'POST', body: { crop_id: Number(cropId || crops[0].id), quantity_kg: qtyNum, harvest_date: date, warehouse_id: Number(warehouseId) } })
      setCreated(batch)
      onCreated()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  if (created) {
    const proof = created.proofs?.[0]
    return (
      <Dialog open={open} onClose={onClose} title={t('ghala.batchReady')}>
        <div className="flex flex-col items-center text-center">
          <QrImage id={created.id} size="lg" />
          <p className="num mt-3 font-mono text-lg font-semibold">{created.id}</p>
          <p className="text-sm text-muted">
            {t(`crops.${created.crop_type}`)} · {f.kg(created.quantity_kg)} · {f.date(created.harvest_date)}
          </p>
          {proof && (
            <p className="mt-2 flex items-center gap-1.5 text-[13px] text-forest-800">
              <CheckCircle2 className="size-4" aria-hidden /> {t('ghala.proofRecorded')}
            </p>
          )}
        </div>
        <div className="mt-5 rounded-md bg-sunken p-4 text-sm">
          <p className="font-semibold">{t('ghala.storedAfterHarvestTitle')}</p>
          <p className="mt-1 text-muted">{t('ghala.storedAfterHarvestBody')}</p>
          <ul className="mt-3 space-y-1.5">
            {(created.warehouse ? [created.warehouse] : [])
              .map((w) => (
                <li key={w.id} className="flex items-center gap-2">
                  <Warehouse className="size-4 text-muted" aria-hidden /> {w.name} · <span className="text-muted">{w.region}</span>
                </li>
              ))}
          </ul>
          {created.receipt && <p className="num mt-2 text-xs text-muted">{created.receipt.id}</p>}
        </div>
        <div className="mt-4 flex gap-2">
          <Button variant="secondary" className="flex-1" onClick={() => window.print()}>
            {t('ghala.printLabel')}
          </Button>
          <Link to={`/ghala/${created.id}`} onClick={onClose} className="inline-flex min-h-11 flex-1 items-center justify-center gap-2 rounded-md bg-forest-800 text-sm font-medium text-white">
            {t('ghala.openBatch')} <ArrowRight className="size-4" aria-hidden />
          </Link>
        </div>
      </Dialog>
    )
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={t('ghala.recordHarvest')}
      footer={
        crops.length > 0 && (
          <>
            <Button variant="secondary" onClick={onClose}>
              {t('common.cancel')}
            </Button>
            <Button type="submit" form="harvest-form" busy={busy} disabled={!qty || !warehouseId}>
              {t('ghala.createBatch')}
            </Button>
          </>
        )
      }
    >
      {!crops.length ? (
        <EmptyState compact icon={Wheat} title={t('ghala.noReadyCrop')} body={t('ghala.noReadyCropBody')} />
      ) : (
        <form id="harvest-form" onSubmit={submit} className="space-y-4" noValidate>
          <Field label={t('farm.crop')}>
            <select className="input" value={cropId} onChange={(e) => setCropId(e.target.value)}>
              {crops.map((c) => (
                <option key={c.id} value={c.id}>
                  {t(`crops.${c.crop_type}`)} · {c.farm_name}
                </option>
              ))}
            </select>
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label={t('ghala.quantityKg')} error={qtyError} hint={t('ghala.quantityHint')}>
              <input className="input num" inputMode="decimal" value={qty} onChange={(e) => setQty(e.target.value)} aria-invalid={Boolean(qtyError)} />
            </Field>
            <Field label={t('ghala.harvestDate')}>
              <input className="input" type="date" value={date} max={new Date().toISOString().slice(0, 10)} onChange={(e) => setDate(e.target.value)} />
            </Field>
          </div>
          <Field label={t('ghala.destinationGhala')}>
            <select className="input" value={warehouseId} onChange={(e) => setWarehouseId(e.target.value)}>
              {verifiedWarehouses.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name} Â· {w.region}
                </option>
              ))}
            </select>
          </Field>
          <p className="text-[13px] text-muted">{t('ghala.batchHint')}</p>
          <ErrorNote text={error} />
        </form>
      )}
    </Dialog>
  )
}
