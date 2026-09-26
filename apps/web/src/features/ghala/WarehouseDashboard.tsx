import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { AlertsPanel } from '../../components/AlertsPanel'
import { TimeSeriesChart } from '../../components/Charts'
import { Button, Card, Empty, ErrorNote, Field, Loading, SimulatedTag, Stat } from '../../components/ui'
import { api } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { useApi, useBi, useErrorText, useFormat } from '../../lib/hooks'
import { BatchCard, type Batch } from './BatchesPage'

type Dashboard = {
  warehouse: { id: number; name: string; region: string; capacity_kg: number }
  stored_kg: number
  batches: Batch[]
  latest: { ts: string; temperature_c: number; humidity_pct: number } | null
  history: { ts: string; temperature_c: number; humidity_pct: number }[]
}

export function WarehouseDashboard() {
  const { t } = useTranslation()
  const f = useFormat()
  const errorText = useErrorText()
  const { user } = useAuth()
  const warehouseId = user?.warehouses?.[0]?.id
  const [tick, setTick] = useState(0)
  const { data, loading, reload } = useApi<Dashboard>(warehouseId ? `/warehouses/${warehouseId}/dashboard` : null, [tick])
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refresh = () => {
    setTick((x) => x + 1)
    reload()
  }
  const scenario = async (name: string) => {
    setBusy(name)
    setError(null)
    try {
      await api(`/demo/scenario/${name}`, { method: 'POST' })
      refresh()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(null)
    }
  }

  if (!warehouseId) return <Empty>{t('ghala.noWarehouse')}</Empty>
  if (loading && !data) return <Loading />
  if (!data) return null
  const inStorage = data.batches.filter((b) => b.status === 'IN_STORAGE')

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">🏚️ {data.warehouse.name}</h1>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat label={t('ghala.temperature')} value={data.latest ? `${f.num(data.latest.temperature_c, 1)}°C` : '—'} sub={data.latest && f.dateTime(data.latest.ts)} />
        <Stat label={t('ghala.humidity')} value={data.latest ? `${f.num(data.latest.humidity_pct, 1)}%` : '—'} />
        <Stat label={t('ghala.stored')} value={`${f.num(data.stored_kg)} kg`} sub={`${t('ghala.capacity')} ${f.num(data.warehouse.capacity_kg)} kg`} />
        <Stat label={t('ghala.batchesInStorage')} value={inStorage.length} />
      </div>

      <IntakeForm warehouseId={warehouseId} onDone={refresh} />

      <Card
        title={t('ghala.monitor')}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <SimulatedTag />
            <Button variant="secondary" className="min-h-8 px-3 text-xs" busy={busy === 'ghala-humid'} onClick={() => scenario('ghala-humid')}>
              💦 {t('ghala.demoHumid')}
            </Button>
            <Button variant="secondary" className="min-h-8 px-3 text-xs" busy={busy === 'ghala-normal'} onClick={() => scenario('ghala-normal')}>
              🌬️ {t('ghala.demoNormal')}
            </Button>
          </div>
        }
      >
        <ErrorNote text={error} />
        {data.history.length ? (
          <TimeSeriesChart
            data={data.history}
            series={[
              { key: 'humidity_pct', label: t('ghala.humidity'), unit: '%', color: '#0369a1', limit: 65 },
              { key: 'temperature_c', label: t('ghala.temperature'), unit: '°C', color: '#c2410c', limit: 27 },
            ]}
          />
        ) : (
          <Empty>{t('farm.noReadings')}</Empty>
        )}
        <p className="mt-2 text-xs text-stone-500">{t('ghala.limitsHint')}</p>
      </Card>

      <AlertsPanel refreshKey={tick} />

      <h2 className="text-lg font-semibold">{t('ghala.batchesTitle')}</h2>
      {data.batches.length ? data.batches.map((b) => <BatchCard key={b.id} batch={b} onChanged={refresh} operator />) : <Empty>{t('ghala.noBatches')}</Empty>}
    </div>
  )
}

function IntakeForm({ warehouseId, onDone }: { warehouseId: number; onDone: () => void }) {
  const { t } = useTranslation()
  const bi = useBi()
  const f = useFormat()
  const errorText = useErrorText()
  const { data: pending, reload } = useApi<any[]>('/warehouses/pending-batches')
  const [batchId, setBatchId] = useState('')
  const [qty, setQty] = useState('')
  const [grade, setGrade] = useState('A')
  const [bay, setBay] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [receipt, setReceipt] = useState<any>(null)

  const selected = pending?.find((p) => p.id === (batchId || pending?.[0]?.id))

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!selected) return
    setBusy(true)
    setError(null)
    try {
      const r = await api(`/warehouses/${warehouseId}/intake`, {
        method: 'POST',
        body: { batch_id: selected.id, quantity_kg: Number(qty || selected.quantity_kg), grade, bay },
      })
      setReceipt(r)
      setQty('')
      setBatchId('')
      reload()
      onDone()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card title={`📥 ${t('ghala.intake')}`}>
      {receipt && (
        <div className="mb-3 rounded-xl bg-green-50 p-3 text-sm">
          <p className="font-semibold">🧾 {t('ghala.receiptIssued', { id: receipt.id })}</p>
          <p className="text-stone-600">
            {f.num(receipt.quantity_kg)} kg · {t('ghala.grade')} {receipt.grade} · {receipt.proofs?.[0]?.mode === 'SIMULATED' ? t('verify.simulatedLedger') : t('verify.onchain')}
          </p>
          <p className="mt-1 text-xs text-stone-500">{bi(receipt.legal_notice)}</p>
        </div>
      )}
      {!pending?.length ? (
        <Empty>{t('ghala.noPending')}</Empty>
      ) : (
        <form onSubmit={submit} className="grid gap-3 sm:grid-cols-5 sm:items-end">
          <Field label={t('ghala.batch')}>
            <select className="input" value={batchId} onChange={(e) => setBatchId(e.target.value)}>
              {pending.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.id} · {p.farmer?.display_name} · {f.num(p.quantity_kg)} kg
                </option>
              ))}
            </select>
          </Field>
          <Field label={t('ghala.weighedKg')}>
            <input className="input" inputMode="decimal" placeholder={selected ? String(selected.quantity_kg) : ''} value={qty} onChange={(e) => setQty(e.target.value)} />
          </Field>
          <Field label={t('ghala.grade')}>
            <select className="input" value={grade} onChange={(e) => setGrade(e.target.value)}>
              {['A', 'B', 'C'].map((g) => (
                <option key={g}>{g}</option>
              ))}
            </select>
          </Field>
          <Field label={t('ghala.bay')}>
            <input className="input" value={bay} onChange={(e) => setBay(e.target.value)} placeholder="A-1" />
          </Field>
          <Button type="submit" busy={busy}>
            {t('ghala.issueReceipt')}
          </Button>
        </form>
      )}
      <ErrorNote text={error} />
    </Card>
  )
}
