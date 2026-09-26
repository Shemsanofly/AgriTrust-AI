import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { TimeSeriesChart } from '../../components/Charts'
import { PinDialog } from '../../components/PinDialog'
import { Badge, Button, Card, Empty, ErrorNote, Field, Loading, RiskBadge, SimulatedTag, VerifyBadge } from '../../components/ui'
import { ApiError, api, apiUrl } from '../../lib/api'
import { useApi, useBi, useErrorText, useFormat, type Bi } from '../../lib/hooks'

type Listing = {
  batch_id: string
  crop_type: string
  grade: string | null
  available_kg: number
  price_per_kg: number
  currency: string
  harvest_date: string
  farmer: { public_id: string; display_name: string; region: string }
  warehouse: { public_id: string; name: string; region: string } | null
  risk: { level: string; drivers: Bi[] }
  verification_status: string
}

const STEP_UP_TZS = 500_000

export function Marketplace() {
  const { t } = useTranslation()
  const f = useFormat()
  const [filters, setFilters] = useState({ crop: '', grade: '', region: '', max_price: '' })
  const [query, setQuery] = useState('')
  const { data, loading } = useApi<Listing[]>(`/marketplace/listings${query}`)

  const apply = (e: FormEvent) => {
    e.preventDefault()
    const params = new URLSearchParams(Object.entries(filters).filter(([, v]) => v))
    setQuery(params.toString() ? `?${params}` : '')
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">🧺 {t('market.title')}</h1>
      <Card>
        <form onSubmit={apply} className="grid grid-cols-2 gap-2 sm:grid-cols-5 sm:items-end">
          <Field label={t('farm.crop')}>
            <select className="input" value={filters.crop} onChange={(e) => setFilters({ ...filters, crop: e.target.value })}>
              <option value="">{t('common.all')}</option>
              {['maize', 'beans', 'rice', 'sorghum', 'sunflower'].map((c) => (
                <option key={c} value={c}>{t(`crops.${c}`)}</option>
              ))}
            </select>
          </Field>
          <Field label={t('ghala.grade')}>
            <select className="input" value={filters.grade} onChange={(e) => setFilters({ ...filters, grade: e.target.value })}>
              <option value="">{t('common.all')}</option>
              {['A', 'B', 'C'].map((g) => (
                <option key={g}>{g}</option>
              ))}
            </select>
          </Field>
          <Field label={t('auth.region')}>
            <input className="input" value={filters.region} onChange={(e) => setFilters({ ...filters, region: e.target.value })} />
          </Field>
          <Field label={t('market.maxPrice')}>
            <input className="input" inputMode="decimal" value={filters.max_price} onChange={(e) => setFilters({ ...filters, max_price: e.target.value })} />
          </Field>
          <Button type="submit" className="col-span-2 sm:col-span-1">
            🔎 {t('market.search')}
          </Button>
        </form>
      </Card>
      <p className="text-xs text-stone-500">{t('market.rankingHint')}</p>
      {loading && !data ? (
        <Loading />
      ) : !data?.length ? (
        <Empty>{t('market.noListings')}</Empty>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {data.map((l) => (
            <Link key={l.batch_id} to={`/market/${l.batch_id}`} className="block rounded-2xl border border-stone-200 bg-white p-4 shadow-sm hover:border-brand-600">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="text-lg font-semibold">
                    {t(`crops.${l.crop_type}`)} {l.grade && <Badge tone="purple">{t('ghala.grade')} {l.grade}</Badge>}
                  </div>
                  <div className="font-mono text-xs text-stone-500">{l.batch_id}</div>
                </div>
                <div className="text-right">
                  <div className="text-lg font-bold text-brand-800">{f.tzs(l.price_per_kg)}</div>
                  <div className="text-xs text-stone-500">/ kg</div>
                </div>
              </div>
              <p className="mt-2 text-sm text-stone-700">
                {f.num(l.available_kg)} kg · {l.warehouse?.name} ({l.warehouse?.region})
              </p>
              <p className="text-sm text-stone-600">
                👩🏾‍🌾 {l.farmer.display_name} · {t('ghala.harvested')} {f.date(l.harvest_date)}
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                <VerifyBadge status={l.verification_status} />
                <span className="text-xs text-stone-500">{t('ghala.spoilageRisk')}:</span>
                <RiskBadge level={l.risk.level} />
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

export function ListingDetail() {
  const { batchId } = useParams()
  const { t } = useTranslation()
  const bi = useBi()
  const f = useFormat()
  const errorText = useErrorText()
  const navigate = useNavigate()
  const { data, loading, error } = useApi<any>(`/marketplace/listings/${batchId}`)
  const [qty, setQty] = useState('')
  const [pinOpen, setPinOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [orderError, setOrderError] = useState<string | null>(null)

  if (loading && !data) return <Loading />
  if (error || !data) return <ErrorNote text={errorText(error)} />

  const total = Number(qty || 0) * data.price_per_kg
  const place = async (pin?: string) => {
    setBusy(true)
    setOrderError(null)
    try {
      await api('/orders', { method: 'POST', body: { batch_id: data.batch_id, quantity_kg: Number(qty), confirm_pin: pin } })
      setPinOpen(false)
      navigate('/orders')
    } catch (err) {
      if (err instanceof ApiError && err.code === 'step_up_required' && !pin) setPinOpen(true)
      else setOrderError(errorText(err))
    } finally {
      setBusy(false)
    }
  }
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (total > STEP_UP_TZS) setPinOpen(true)
    else place()
  }

  return (
    <div className="space-y-4">
      <Link to="/" className="text-sm text-brand-800 underline">
        ← {t('market.back')}
      </Link>
      <Card>
        <div className="flex flex-wrap gap-4">
          <img src={apiUrl(`/qr/${data.batch_id}.svg`)} alt="QR" className="h-24 w-24 rounded-lg border" />
          <div className="min-w-0 flex-1">
            <h1 className="text-xl font-bold">
              {t(`crops.${data.crop_type}`)} · {t('ghala.grade')} {data.grade}
            </h1>
            <p className="font-mono text-sm text-stone-500">{data.batch_id}</p>
            <p className="mt-1 text-sm">
              👩🏾‍🌾 {data.farmer.display_name} ({data.farmer.public_id}) · {data.farmer.region}
            </p>
            <p className="text-sm">🏚️ {data.warehouse?.name} · {data.warehouse?.region}</p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <VerifyBadge status={data.verification_status} />
              <RiskBadge level={data.risk.level} />
              <Link to={`/verify/${data.batch_id}`} className="text-sm text-brand-800 underline">
                {t('market.seeJourney')}
              </Link>
            </div>
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold text-brand-800">{f.tzs(data.price_per_kg)}</div>
            <div className="text-sm text-stone-500">/ kg · {f.num(data.available_kg)} kg</div>
          </div>
        </div>
      </Card>

      <Card title={`🏚️ ${t('market.digitalGhala')}`} actions={<SimulatedTag label={t('market.sensorsSimulated')} />}>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {data.digital_ghala.map((b: any) => (
            <div key={b.batch_id} className={`rounded-xl border-2 p-3 text-sm ${b.batch_id === data.batch_id ? 'border-brand-600 bg-brand-50' : 'border-stone-200 bg-stone-50'}`}>
              <div className="text-2xl" aria-hidden>
                {'🟫'.repeat(Math.min(5, Math.max(1, Math.round(b.available_kg / 500))))}
              </div>
              <div className="mt-1 font-mono text-xs">{b.batch_id}</div>
              <div>
                {t(`crops.${b.crop_type}`)} · {b.grade}
              </div>
              <div className="font-semibold">{f.num(b.available_kg)} kg</div>
              <RiskBadge level={b.risk} />
            </div>
          ))}
        </div>
        {data.risk.drivers?.length > 0 && (
          <ul className="mt-3 list-disc pl-5 text-sm text-stone-700">
            {data.risk.drivers.map((d: Bi, i: number) => (
              <li key={i}>{bi(d)}</li>
            ))}
          </ul>
        )}
      </Card>

      <Card title={t('market.storageHistory')}>
        {data.storage_history.length ? (
          <TimeSeriesChart
            data={data.storage_history}
            series={[
              { key: 'humidity_pct', label: t('ghala.humidity'), unit: '%', color: '#0369a1', limit: 65 },
              { key: 'temperature_c', label: t('ghala.temperature'), unit: '°C', color: '#c2410c', limit: 27 },
            ]}
          />
        ) : (
          <Empty>{t('farm.noReadings')}</Empty>
        )}
      </Card>

      <Card title={`🛒 ${t('market.placeOrder')}`}>
        <form onSubmit={submit} className="flex flex-wrap items-end gap-3">
          <Field label={t('ghala.quantityKg')}>
            <input className="input w-40" inputMode="decimal" value={qty} onChange={(e) => setQty(e.target.value)} required />
          </Field>
          <div className="pb-2 text-sm">
            {t('market.total')}: <b>{f.tzs(total)}</b>
          </div>
          <Button type="submit" busy={busy} disabled={!qty || Number(qty) > data.available_kg}>
            {t('market.order')}
          </Button>
        </form>
        <p className="mt-2 text-xs text-stone-500">
          {t('market.paymentSimulated')} <SimulatedTag />
        </p>
        <ErrorNote text={orderError} />
      </Card>
      <PinDialog open={pinOpen} busy={busy} title={t('pin.confirmOrder')} description={t('pin.largeOrder', { amount: f.tzs(total) })} onCancel={() => setPinOpen(false)} onConfirm={(pin) => place(pin)} />
    </div>
  )
}
