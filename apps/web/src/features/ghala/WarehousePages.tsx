import { ArrowRight, CheckCircle2, Droplets, FlaskConical, PackagePlus, Thermometer, Wind } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { AlertsPanel } from '../../components/AlertsPanel'
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
  PageHeader,
  ProgressBar,
  RiskBadge,
  Segmented,
  SimulatedTag,
  Stat,
  StatStrip,
  cx,
  useToast,
} from '../../components/ui'
import { api } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { useApi, useBi, useErrorText, useFormat } from '../../lib/hooks'
import type { Batch } from '../farmer/shared'
import { BatchRow, QrImage } from './BatchParts'

type Dashboard = {
  warehouse: { id: number; name: string; region: string; capacity_kg: number; public_id: string }
  stored_kg: number
  batches: (Batch & { owner?: { display_name: string; public_id: string; cooperative?: string } })[]
  latest: { ts: string; temperature_c: number; humidity_pct: number } | null
  history: { ts: string; temperature_c: number; humidity_pct: number }[]
}

function useDashboard(tick = 0) {
  const { user } = useAuth()
  const id = user?.warehouses?.[0]?.id
  return { id, ...useApi<Dashboard>(id ? `/warehouses/${id}/dashboard` : null, [tick]) }
}

export function WarehouseOverview() {
  const { t } = useTranslation()
  const bi = useBi()
  const f = useFormat()
  const toast = useToast()
  const errorText = useErrorText()
  const [tick, setTick] = useState(0)
  const { id, data, loading, error, reload } = useDashboard(tick)
  const [busy, setBusy] = useState<string | null>(null)

  const scenario = async (name: string, done: string) => {
    setBusy(name)
    try {
      await api(`/demo/scenario/${name}`, { method: 'POST' })
      setTick((x) => x + 1)
      toast(done, 'info')
    } finally {
      setBusy(null)
    }
  }

  if (!id) return <EmptyState title={t('ghala.noWarehouse')} />
  if (loading && !data) return <Loading rows={4} />
  if (error || !data) return <ErrorState text={errorText(error)} onRetry={reload} />

  const stored = data.batches.filter((b) => b.status === 'IN_STORAGE')
  const counts = { HIGH: 0, MEDIUM: 0, LOW: 0 } as Record<string, number>
  for (const b of stored) if (b.risk?.level && b.risk.level in counts) counts[b.risk.level]++
  const worst = stored.filter((b) => b.risk?.level === 'HIGH')
  const used = data.warehouse.capacity_kg ? data.stored_kg / data.warehouse.capacity_kg : 0
  const rh = data.latest?.humidity_pct
  const temp = data.latest?.temperature_c

  return (
    <div className="space-y-5">
      <PageHeader eyebrow={`${data.warehouse.public_id} · ${data.warehouse.region}`} title={data.warehouse.name} subtitle={t('ghala.overviewSubtitle')} />

      {worst.length > 0 && (
        <Notice tone="danger" title={bi(worst[0].risk!.headline)}>
          {bi(worst[0].risk!.action)} ·{' '}
          <Link to={`/stock/${worst[0].id}`} className="font-medium underline">
            {t('ghala.batchesAffected', { count: worst.length })}
          </Link>
        </Notice>
      )}

      <StatStrip>
        <Stat icon={Thermometer} label={t('ghala.temperature')} value={temp != null ? `${f.num(temp, 1)}°C` : '—'} sub={temp != null && temp >= 27 ? t('ghala.aboveSafe', { limit: '27°C' }) : t('ghala.safeBelow', { limit: '27°C' })} tone={temp != null && temp >= 30 ? 'red' : temp != null && temp >= 27 ? 'amber' : undefined} />
        <Stat icon={Droplets} label={t('ghala.humidity')} value={rh != null ? `${f.num(rh, 1)}%` : '—'} sub={rh != null && rh >= 65 ? t('ghala.aboveSafe', { limit: '65%' }) : t('ghala.safeBelow', { limit: '65%' })} tone={rh != null && rh >= 75 ? 'red' : rh != null && rh >= 65 ? 'amber' : undefined} />
        <Stat label={t('ghala.stored')} value={f.kg(data.stored_kg)} sub={t('ghala.capacityUsed', { pct: Math.round(used * 100) })} />
        <Stat label={t('ghala.riskMix')} value={<span className="flex gap-1.5 text-base">{(['HIGH', 'MEDIUM', 'LOW'] as const).map((l) => counts[l] > 0 && <RiskBadge key={l} level={l} prefix={`${counts[l]} · `} />)}{!stored.length && '—'}</span>} sub={t('ghala.batchCount', { count: stored.length })} />
      </StatStrip>

      <div className="grid gap-5 lg:grid-cols-[1.5fr_1fr]">
        <Card
          title={t('ghala.monitor')}
          subtitle={data.latest ? t('farm.lastSeen', { time: f.relative(data.latest.ts) }) : undefined}
          actions={
            <div className="flex items-center gap-2">
              <SimulatedTag label={t('ghala.sensorSimulated')} />
            </div>
          }
        >
          {data.history.length ? (
            <div className="space-y-4">
              <TimeSeriesChart height={180} data={data.history} series={[{ key: 'humidity_pct', label: t('ghala.humidity'), unit: '%', color: CHART.humidity, limit: 65 }]} />
              <TimeSeriesChart height={140} data={data.history} series={[{ key: 'temperature_c', label: t('ghala.temperature'), unit: '°C', color: CHART.temperature, limit: 27 }]} />
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
          <details className="mt-4 text-[13px]">
            <summary className="inline-flex cursor-pointer items-center gap-1.5 text-muted hover:text-ink">
              <FlaskConical className="size-3.5" aria-hidden /> {t('demo.controls')}
            </summary>
            <div className="mt-2 flex flex-wrap gap-2">
              <Button size="sm" variant="secondary" icon={Droplets} busy={busy === 'ghala-humid'} onClick={() => scenario('ghala-humid', t('demo.humidDone'))}>
                {t('demo.humidityRising')}
              </Button>
              <Button size="sm" variant="secondary" icon={Wind} busy={busy === 'ghala-normal'} onClick={() => scenario('ghala-normal', t('demo.ventilatedDone'))}>
                {t('demo.ventilated')}
              </Button>
            </div>
          </details>
        </Card>

        <div className="space-y-5">
          <AlertsPanel refreshKey={tick} limit={4} />
          <Card title={t('ghala.capacity')}>
            <ProgressBar value={data.stored_kg} max={data.warehouse.capacity_kg} tone={used > 0.9 ? 'red' : used > 0.75 ? 'gold' : 'green'} label={t('ghala.capacity')} />
            <p className="num mt-2 text-[13px] text-muted">
              {f.kg(data.stored_kg)} / {f.kg(data.warehouse.capacity_kg)}
            </p>
            <Link to="/intake" className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-forest-800">
              <PackagePlus className="size-4" aria-hidden /> {t('ghala.intake')}
            </Link>
          </Card>
        </div>
      </div>

      <Card title={t('ghala.storedTitle')} padded={false} actions={<Link to="/stock" className="text-sm font-medium text-forest-800">{t('common.viewAll')}</Link>}>
        {stored.length ? (
          <ul className="divide-y divide-line">
            {stored.slice(0, 5).map((b) => (
              <BatchRow key={b.id} batch={{ ...b, owner: b.owner?.display_name }} to={`/stock/${b.id}`} showOwner />
            ))}
          </ul>
        ) : (
          <EmptyState compact title={t('ghala.nothingStored')} />
        )}
      </Card>
    </div>
  )
}

export function WarehouseStockPage() {
  const { t } = useTranslation()
  const f = useFormat()
  const errorText = useErrorText()
  const { id, data, loading, error, reload } = useDashboard()
  const [filter, setFilter] = useState<'all' | 'HIGH' | 'listed'>('all')
  if (!id) return <EmptyState title={t('ghala.noWarehouse')} />
  const stored = (data?.batches ?? []).filter((b) => b.status === 'IN_STORAGE')
  const rows = stored.filter((b) => (filter === 'HIGH' ? b.risk?.level === 'HIGH' : filter === 'listed' ? b.listed : true))

  return (
    <div>
      <PageHeader title={t('nav.stock')} subtitle={t('ghala.stockSubtitle')} />
      <div className="mb-4">
        <Segmented
          label={t('common.filter')}
          value={filter}
          onChange={setFilter}
          options={[
            { id: 'all', label: t('ghala.filterAll', { count: stored.length }) },
            { id: 'HIGH', label: t('ghala.filterHigh') },
            { id: 'listed', label: t('ghala.filterListed') },
          ]}
        />
      </div>
      {loading && !data ? (
        <Loading />
      ) : error ? (
        <ErrorState text={errorText(error)} onRetry={reload} />
      ) : !rows.length ? (
        <Card>
          <EmptyState title={t('ghala.noMatch')} />
        </Card>
      ) : (
        <>
          <Card padded={false} className="lg:hidden">
            <ul className="divide-y divide-line">
              {rows.map((b) => (
                <BatchRow key={b.id} batch={{ ...b, owner: b.owner?.display_name }} to={`/stock/${b.id}`} showOwner />
              ))}
            </ul>
          </Card>
          <Card padded={false} className="hidden overflow-hidden lg:block">
            <table className="w-full text-left text-sm">
              <thead className="bg-sunken text-xs text-muted">
                <tr>
                  <th className="px-5 py-2.5 font-medium">{t('ghala.batch')}</th>
                  <th className="px-3 py-2.5 font-medium">{t('ghala.owner')}</th>
                  <th className="px-3 py-2.5 text-right font-medium">{t('ghala.quantity')}</th>
                  <th className="px-3 py-2.5 font-medium">{t('ghala.grade')}</th>
                  <th className="px-3 py-2.5 text-right font-medium">{t('ghala.storageDuration')}</th>
                  <th className="px-3 py-2.5 text-right font-medium">{t('ghala.tempRh')}</th>
                  <th className="px-5 py-2.5 font-medium">{t('ghala.spoilageRisk')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {rows.map((b) => (
                  <tr key={b.id} className="hover:bg-sunken/50">
                    <td className="px-5 py-3">
                      <Link to={`/stock/${b.id}`} className="flex items-center gap-3">
                        <CropImage crop={b.crop_type} className="size-9" />
                        <span>
                          <span className="block font-medium">{t(`crops.${b.crop_type}`)}</span>
                          <span className="num font-mono text-xs text-muted">{b.id}</span>
                        </span>
                      </Link>
                    </td>
                    <td className="px-3 py-3">
                      {b.owner?.display_name}
                      {b.owner?.cooperative && <span className="block text-xs text-muted">{b.owner.cooperative}</span>}
                    </td>
                    <td className="num px-3 py-3 text-right">{f.kg(b.available_kg)}</td>
                    <td className="px-3 py-3">{b.grade && <Badge tone="gold">{b.grade}</Badge>}</td>
                    <td className="num px-3 py-3 text-right">{t('ghala.daysShort', { count: b.days_in_storage ?? 0 })}</td>
                    <td className="num px-3 py-3 text-right text-muted">
                      {b.risk?.stats?.temp_avg != null ? `${f.num(b.risk.stats.temp_avg, 1)}° · ${f.num(b.risk.stats.rh_avg, 0)}%` : '—'}
                    </td>
                    <td className="px-5 py-3">
                      <RiskBadge level={b.risk?.level} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </>
      )}
    </div>
  )
}

const GRADE_HINT = { A: 'ghala.gradeA', B: 'ghala.gradeB', C: 'ghala.gradeC' } as const

export function IntakePage() {
  const { t } = useTranslation()
  const bi = useBi()
  const f = useFormat()
  const toast = useToast()
  const errorText = useErrorText()
  const { user } = useAuth()
  const warehouseId = user?.warehouses?.[0]?.id
  const { data: pending, loading, reload } = useApi<any[]>('/warehouses/pending-batches')
  const [selected, setSelected] = useState<string | null>(null)
  const [qty, setQty] = useState('')
  const [grade, setGrade] = useState<'A' | 'B' | 'C'>('A')
  const [bay, setBay] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [receipt, setReceipt] = useState<any>(null)
  const batch = pending?.find((p) => p.id === selected)
  const qtyNum = Number(qty.replace(',', '.'))

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!batch) return
    if (!(qtyNum > 0)) return setError(t('validation.quantity'))
    setBusy(true)
    setError(null)
    try {
      const r = await api(`/warehouses/${warehouseId}/intake`, { method: 'POST', body: { batch_id: batch.id, quantity_kg: qtyNum, grade, bay: bay.trim() } })
      setReceipt(r)
      setSelected(null)
      setQty('')
      setBay('')
      toast(t('ghala.receiptIssued', { id: r.id }))
      reload()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <PageHeader title={t('ghala.intake')} subtitle={t('ghala.intakeSubtitle')} />
      {receipt && (
        <Card className="mb-5">
          <div className="flex flex-wrap items-center gap-5">
            <QrImage id={receipt.id} />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 text-forest-800">
                <CheckCircle2 className="size-5" aria-hidden />
                <span className="font-semibold">{t('ghala.receiptIssued', { id: receipt.id })}</span>
              </div>
              <div className="mt-2">
                <KeyValues
                  cols={3}
                  items={[
                    [t('ghala.batch'), <span className="num font-mono">{receipt.batch_id}</span>],
                    [t('ghala.owner'), receipt.owner?.display_name],
                    [t('ghala.weighedIn'), f.kg(receipt.quantity_kg)],
                    [t('ghala.grade'), receipt.grade],
                    [t('ghala.bay'), receipt.bay || '—'],
                    [t('verify.proof'), receipt.proofs?.[0]?.mode === 'SIMULATED' ? t('verify.localLedger') : t('verify.onchain')],
                  ]}
                />
              </div>
              <p className="mt-3 text-xs text-muted">{bi(receipt.legal_notice)}</p>
            </div>
            <Link to={`/stock/${receipt.batch_id}`} className="inline-flex items-center gap-1.5 text-sm font-medium text-forest-800">
              {t('ghala.openBatch')} <ArrowRight className="size-4" aria-hidden />
            </Link>
          </div>
        </Card>
      )}
      <div className="grid gap-5 lg:grid-cols-[1fr_1.1fr]">
        <Card title={t('ghala.waitingForIntake')} padded={false}>
          {loading && !pending ? (
            <div className="p-4">
              <Loading rows={2} />
            </div>
          ) : !pending?.length ? (
            <EmptyState icon={PackagePlus} title={t('ghala.noPending')} body={t('ghala.noPendingBody')} />
          ) : (
            <ul className="divide-y divide-line" role="listbox" aria-label={t('ghala.waitingForIntake')}>
              {pending.map((p) => (
                <li key={p.id}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={selected === p.id}
                    onClick={() => {
                      setSelected(p.id)
                      setQty(String(p.quantity_kg))
                    }}
                    className={cx('flex w-full items-center gap-3 px-4 py-3 text-left sm:px-5', selected === p.id ? 'bg-forest-50' : 'hover:bg-sunken/60')}
                  >
                    <CropImage crop={p.crop_type} className="size-11" />
                    <div className="min-w-0 flex-1">
                      <div className="font-medium">
                        {t(`crops.${p.crop_type}`)} · <span className="num">{f.kg(p.quantity_kg)}</span>
                      </div>
                      <div className="text-[13px] text-muted">
                        <span className="num font-mono">{p.id}</span> · {p.farmer?.display_name} · {f.date(p.harvest_date)}
                      </div>
                    </div>
                    {selected === p.id && <CheckCircle2 className="size-5 text-forest-700" aria-hidden />}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title={t('ghala.recordIntake')} subtitle={batch ? `${batch.id} · ${batch.farmer?.display_name}` : t('ghala.selectBatch')}>
          <form onSubmit={submit} className="space-y-4">
            <Field label={t('ghala.weighedKg')} hint={batch ? t('ghala.farmerRecorded', { kg: f.kg(batch.quantity_kg) }) : undefined}>
              <input className="input num" inputMode="decimal" disabled={!batch} value={qty} onChange={(e) => setQty(e.target.value)} />
            </Field>
            <fieldset disabled={!batch}>
              <legend className="label">{t('ghala.grade')}</legend>
              <div className="grid grid-cols-3 gap-2">
                {(['A', 'B', 'C'] as const).map((g) => (
                  <label key={g} className={cx('cursor-pointer rounded-md border p-3 text-sm', grade === g ? 'border-forest-700 bg-forest-50' : 'border-line-strong')}>
                    <input type="radio" name="grade" className="sr-only" checked={grade === g} onChange={() => setGrade(g)} />
                    <span className="block font-semibold">{t('ghala.gradeX', { grade: g })}</span>
                    <span className="block text-xs text-muted">{t(GRADE_HINT[g])}</span>
                  </label>
                ))}
              </div>
            </fieldset>
            <Field label={t('ghala.bay')} optional>
              <input className="input" disabled={!batch} value={bay} onChange={(e) => setBay(e.target.value)} placeholder="A-1" />
            </Field>
            <ErrorNote text={error} />
            <Button type="submit" busy={busy} disabled={!batch}>
              {t('ghala.issueReceipt')}
            </Button>
            <p className="text-xs text-muted">{t('ghala.receiptLegal')}</p>
          </form>
        </Card>
      </div>
    </div>
  )
}
