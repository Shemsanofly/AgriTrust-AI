import { ArrowLeft, CalendarDays, Clock, MapPin, Search, ShieldCheck, SlidersHorizontal, Sparkles, Users, Warehouse, X } from 'lucide-react'
import { useMemo, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ChartLegend, CHART, TimeSeriesChart } from '../../components/Charts'
import { ConfirmAction } from '../../components/ConfirmAction'
import { CropImage } from '../../components/crops'
import {
  Badge,
  Button,
  Card,
  Dialog,
  EmptyState,
  ErrorNote,
  ErrorState,
  Field,
  KeyValues,
  Loading,
  PageHeader,
  RiskBadge,
  SimulatedTag,
  VerifyBadge,
  cx,
  useToast,
} from '../../components/ui'
import { ApiError, api } from '../../lib/api'
import { useApi, useBi, useErrorText, useFormat, type Bi } from '../../lib/hooks'
import { QrImage } from '../ghala/BatchParts'

export type Listing = {
  batch_id: string
  crop_type: string
  grade: string | null
  available_kg: number
  price_per_kg: number
  currency: string
  harvest_date: string
  date_in: string | null
  days_in_storage: number | null
  receipt_id: string | null
  farmer: { public_id: string; display_name: string; region: string; district?: string; cooperative?: string | null }
  warehouse: { public_id: string; name: string; region: string } | null
  risk: { level: string; headline: Bi; drivers: Bi[]; stats?: Record<string, number> }
  verification_status: string
}

const CROPS = ['maize', 'rice', 'beans', 'sorghum', 'sunflower']
type Sort = 'match' | 'price' | 'quantity' | 'fresh'

export function Marketplace() {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const { data, loading, error, reload } = useApi<Listing[]>('/marketplace/listings')
  const [q, setQ] = useState('')
  const [crop, setCrop] = useState('')
  const [grade, setGrade] = useState('')
  const [region, setRegion] = useState('')
  const [maxPrice, setMaxPrice] = useState('')
  const [verifiedOnly, setVerifiedOnly] = useState(false)
  const [sort, setSort] = useState<Sort>('match')
  const [filtersOpen, setFiltersOpen] = useState(false)

  const regions = useMemo(() => [...new Set((data ?? []).map((l) => l.warehouse?.region).filter(Boolean))] as string[], [data])
  const rows = useMemo(() => {
    const term = q.trim().toLowerCase()
    const filtered = (data ?? []).filter(
      (l) =>
        (!crop || l.crop_type === crop) &&
        (!grade || l.grade === grade) &&
        (!region || l.warehouse?.region === region) &&
        (!maxPrice || l.price_per_kg <= Number(maxPrice)) &&
        (!verifiedOnly || l.verification_status === 'VERIFIED') &&
        (!term ||
          [t(`crops.${l.crop_type}`), l.crop_type, l.farmer.display_name, l.farmer.cooperative, l.warehouse?.name, l.warehouse?.region, l.batch_id]
            .filter(Boolean)
            .some((s) => String(s).toLowerCase().includes(term))),
    )
    // Default order comes from the API's buyer-matching rules.
    if (sort === 'price') return [...filtered].sort((a, b) => a.price_per_kg - b.price_per_kg)
    if (sort === 'quantity') return [...filtered].sort((a, b) => b.available_kg - a.available_kg)
    if (sort === 'fresh') return [...filtered].sort((a, b) => b.harvest_date.localeCompare(a.harvest_date))
    return filtered
  }, [data, q, crop, grade, region, maxPrice, verifiedOnly, sort, t])

  const activeFilters = [grade, region, maxPrice, verifiedOnly ? 'v' : ''].filter(Boolean).length
  const clear = () => {
    setGrade('')
    setRegion('')
    setMaxPrice('')
    setVerifiedOnly(false)
  }

  const filterFields = (
    <div className="grid gap-4">
      <Field label={t('ghala.grade')}>
        <select className="input" value={grade} onChange={(e) => setGrade(e.target.value)}>
          <option value="">{t('common.any')}</option>
          {['A', 'B', 'C'].map((g) => (
            <option key={g} value={g}>
              {t('ghala.gradeX', { grade: g })}
            </option>
          ))}
        </select>
      </Field>
      <Field label={t('market.region')}>
        <select className="input" value={region} onChange={(e) => setRegion(e.target.value)}>
          <option value="">{t('common.any')}</option>
          {regions.map((r) => (
            <option key={r}>{r}</option>
          ))}
        </select>
      </Field>
      <Field label={t('market.maxPrice')}>
        <input className="input num" inputMode="numeric" value={maxPrice} onChange={(e) => setMaxPrice(e.target.value.replace(/\D/g, ''))} placeholder="TZS / kg" />
      </Field>
      <label className="flex min-h-11 items-center gap-2 text-sm">
        <input type="checkbox" className="size-4 accent-forest-800" checked={verifiedOnly} onChange={(e) => setVerifiedOnly(e.target.checked)} />
        {t('market.verifiedOnly')}
      </label>
    </div>
  )

  return (
    <div>
      <PageHeader title={t('market.title')} subtitle={t('market.subtitle')} />

      <div className="flex gap-2">
        <label className="relative min-w-0 flex-1">
          <span className="sr-only">{t('market.search')}</span>
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted" aria-hidden />
          <input className="input pl-9" type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('market.searchPlaceholder')} />
        </label>
        <Button variant="secondary" icon={SlidersHorizontal} onClick={() => setFiltersOpen(true)} className="lg:hidden">
          {activeFilters ? `${t('common.filters')} · ${activeFilters}` : t('common.filters')}
        </Button>
        <select className="input hidden w-48 lg:block" value={sort} onChange={(e) => setSort(e.target.value as Sort)} aria-label={t('market.sort')}>
          {(['match', 'price', 'quantity', 'fresh'] as Sort[]).map((s) => (
            <option key={s} value={s}>
              {t(`market.sortBy.${s}`)}
            </option>
          ))}
        </select>
      </div>

      <div className="-mx-4 mt-3 flex gap-2 overflow-x-auto px-4 pb-1 sm:mx-0 sm:px-0" role="group" aria-label={t('farm.crop')}>
        {['', ...CROPS].map((c) => (
          <button
            key={c || 'all'}
            type="button"
            aria-pressed={crop === c}
            onClick={() => setCrop(c)}
            className={cx('min-h-9 shrink-0 rounded-md border px-3 text-[13px] font-medium', crop === c ? 'border-forest-800 bg-forest-800 text-white' : 'border-line-strong bg-surface text-ink-soft hover:bg-sunken')}
          >
            {c ? t(`crops.${c}`) : t('common.all')}
          </button>
        ))}
      </div>

      <div className="mt-5 grid gap-6 lg:grid-cols-[14rem_1fr]">
        <aside className="hidden lg:block">
          <div className="sticky top-4 space-y-4">
            {filterFields}
            {activeFilters > 0 && (
              <Button variant="ghost" size="sm" icon={X} onClick={clear}>
                {t('common.clearFilters')}
              </Button>
            )}
          </div>
        </aside>

        <div>
          <p className="mb-3 text-[13px] text-muted">
            {loading && !data ? t('common.loading') : t('market.resultCount', { count: rows.length })}
            {sort === 'match' && rows.length > 1 && <> · {t('market.rankingHint')}</>}
          </p>
          {loading && !data ? (
            <Loading rows={3} />
          ) : error ? (
            <ErrorState text={errorText(error)} onRetry={reload} />
          ) : !rows.length ? (
            <Card>
              <EmptyState icon={Search} title={t('market.noListings')} body={t('market.noListingsBody')} action={activeFilters > 0 || crop || q ? <Button variant="secondary" onClick={() => (clear(), setCrop(''), setQ(''))}>{t('common.clearFilters')}</Button> : undefined} />
            </Card>
          ) : (
            <ul className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-3">
              {rows.map((l, i) => (
                <ListingCard key={l.batch_id} listing={l} bestMatch={sort === 'match' && i === 0 && rows.length > 1} />
              ))}
            </ul>
          )}
        </div>
      </div>

      <Dialog
        open={filtersOpen}
        onClose={() => setFiltersOpen(false)}
        title={t('common.filters')}
        footer={
          <>
            <Button variant="ghost" onClick={clear}>
              {t('common.clearFilters')}
            </Button>
            <Button onClick={() => setFiltersOpen(false)}>{t('market.showResults', { count: rows.length })}</Button>
          </>
        }
      >
        <div className="space-y-4">
          <Field label={t('market.sort')}>
            <select className="input" value={sort} onChange={(e) => setSort(e.target.value as Sort)}>
              {(['match', 'price', 'quantity', 'fresh'] as Sort[]).map((s) => (
                <option key={s} value={s}>
                  {t(`market.sortBy.${s}`)}
                </option>
              ))}
            </select>
          </Field>
          {filterFields}
        </div>
      </Dialog>
    </div>
  )
}

function ListingCard({ listing: l, bestMatch }: { listing: Listing; bestMatch: boolean }) {
  const { t } = useTranslation()
  const f = useFormat()
  return (
    <li>
      <Link to={`/market/${l.batch_id}`} className="group flex h-full flex-col overflow-hidden rounded-(--radius-card) border border-line bg-surface hover:border-line-strong">
        <div className="relative">
          <CropImage crop={l.crop_type} rounded={false} className="aspect-[16/9] w-full" />
          {l.verification_status === 'VERIFIED' && (
            <span className="absolute top-2 left-2 inline-flex items-center gap-1 rounded bg-surface/95 px-1.5 py-0.5 text-xs font-medium text-forest-800">
              <ShieldCheck className="size-3.5" aria-hidden /> {t('verify.status.VERIFIED')}
            </span>
          )}
          {bestMatch && (
            <span className="absolute top-2 right-2 inline-flex items-center gap-1 rounded bg-harvest-500 px-1.5 py-0.5 text-xs font-semibold text-forest-950" title={t('market.bestMatchWhy')}>
              <Sparkles className="size-3.5" aria-hidden /> {t('market.bestMatch')}
            </span>
          )}
        </div>
        <div className="flex flex-1 flex-col p-4">
          <div className="flex items-center justify-between gap-2">
            <span className="font-semibold">{t(`crops.${l.crop_type}`)}</span>
            {l.grade && <Badge tone="gold">{t('ghala.gradeX', { grade: l.grade })}</Badge>}
          </div>
          <div className="num mt-1 flex items-baseline justify-between gap-2">
            <span>
              <span className="text-lg font-semibold">{f.tzs(l.price_per_kg)}</span> <span className="text-xs text-muted">/ kg</span>
            </span>
            <span className="text-[13px] text-muted">{t('market.available', { kg: f.kg(l.available_kg) })}</span>
          </div>
          <dl className="mt-3 space-y-1.5 text-[13px] text-ink-soft">
            <div className="flex items-center gap-2">
              <MapPin className="size-3.5 shrink-0 text-muted" aria-hidden />
              <dd className="truncate">
                {l.warehouse?.name} · {l.warehouse?.region}
              </dd>
            </div>
            <div className="flex items-center gap-2">
              <Users className="size-3.5 shrink-0 text-muted" aria-hidden />
              <dd className="truncate">{l.farmer.cooperative ?? l.farmer.display_name}</dd>
            </div>
            <div className="flex items-center gap-2">
              <CalendarDays className="size-3.5 shrink-0 text-muted" aria-hidden />
              <dd>
                {t('market.harvested', { date: f.date(l.harvest_date) })} · {t('ghala.daysStored', { count: l.days_in_storage ?? 0 })}
              </dd>
            </div>
          </dl>
          <div className="mt-auto flex items-center gap-2 pt-3">
            <span className="text-xs text-muted">{t('market.storage')}</span>
            <RiskBadge level={l.risk.level} />
          </div>
        </div>
      </Link>
    </li>
  )
}

export function ListingDetail() {
  const { batchId } = useParams()
  const { t } = useTranslation()
  const bi = useBi()
  const f = useFormat()
  const toast = useToast()
  const navigate = useNavigate()
  const errorText = useErrorText()
  const { data, loading, error, reload } = useApi<Listing & { storage_history: any[]; digital_ghala: any[]; verification: { status: string; checks: any[] } }>(`/marketplace/listings/${batchId}`)
  const [qty, setQty] = useState('')
  const [confirm, setConfirm] = useState(false)
  const [busy, setBusy] = useState(false)
  const [orderError, setOrderError] = useState<string | null>(null)

  if (loading && !data) return <Loading rows={4} />
  if (error || !data) return <ErrorState text={errorText(error)} onRetry={reload} />

  const qtyNum = Number(qty.replace(/[, ]/g, ''))
  const total = qtyNum * data.price_per_kg
  // Only complain when the buyer asks for more than is stored; the amount itself is shown as a hint.
  const qtyError = !qty ? null : !(qtyNum > 0) ? t('validation.quantity') : qtyNum > data.available_kg ? t('validation.qtyMax', { kg: f.kg(data.available_kg) }) : null
  // Quick-fill shares, rounded to 0.5 kg; shares that would be 0 kg are not offered.
  const shares = [0.25, 0.5, 1]
    .map((share) => ({ share, kg: share === 1 ? data.available_kg : Math.floor(data.available_kg * share * 2) / 2 }))
    .filter((x) => x.kg > 0 && (x.share === 1 || x.kg < data.available_kg))

  const place = async (pin?: string) => {
    setBusy(true)
    setOrderError(null)
    try {
      await api('/orders', { method: 'POST', body: { batch_id: data.batch_id, quantity_kg: qtyNum, confirm_pin: pin } })
      toast(t('market.requestSent'))
      navigate('/orders')
    } catch (err) {
      if (err instanceof ApiError && err.code === 'step_up_required' && !pin) setConfirm(true)
      else if (pin) throw err
      else setOrderError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!(qtyNum > 0) || qtyError) return setOrderError(t('validation.quantity'))
    if (total > 500_000) setConfirm(true)
    else place()
  }

  return (
    <div className="space-y-5">
      <Link to="/" className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink">
        <ArrowLeft className="size-4" aria-hidden /> {t('market.back')}
      </Link>

      <div className="grid gap-5 lg:grid-cols-[1.4fr_1fr]">
        <div className="space-y-5">
          <Card padded={false} className="overflow-hidden">
            <CropImage crop={data.crop_type} rounded={false} className="aspect-[21/9] w-full" />
            <div className="p-4 sm:p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h1 className="text-[22px] font-semibold tracking-tight">
                    {t(`crops.${data.crop_type}`)} · {t('ghala.gradeX', { grade: data.grade })}
                  </h1>
                  <p className="num font-mono text-sm text-muted">{data.batch_id}</p>
                </div>
                <div className="num text-right">
                  <div className="text-2xl font-semibold">{f.tzs(data.price_per_kg)}</div>
                  <div className="text-sm text-muted">/ kg</div>
                </div>
              </div>
              <div className="mt-4">
                <KeyValues
                  cols={3}
                  items={[
                    [t('market.availableLabel'), f.kg(data.available_kg)],
                    [t('ghala.harvestDate'), f.date(data.harvest_date)],
                    [t('ghala.storageDuration'), t('ghala.daysShort', { count: data.days_in_storage ?? 0 })],
                    [t('ghala.warehouse'), data.warehouse?.name],
                    [t('market.region'), data.warehouse?.region],
                    [t('ghala.receiptNo'), <span className="num font-mono">{data.receipt_id ?? '—'}</span>],
                  ]}
                />
              </div>
            </div>
          </Card>

          <Card title={t('market.storageCondition')} subtitle={bi(data.risk.headline)} actions={<RiskBadge level={data.risk.level} />}>
            {data.storage_history.length ? (
              <>
                <TimeSeriesChart height={150} data={data.storage_history} series={[{ key: 'humidity_pct', label: t('ghala.humidity'), unit: '%', color: CHART.humidity, limit: 65 }]} />
                <TimeSeriesChart height={120} data={data.storage_history} series={[{ key: 'temperature_c', label: t('ghala.temperature'), unit: '°C', color: CHART.temperature, limit: 27 }]} />
                <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                  <ChartLegend items={[{ label: t('ghala.humidity'), color: CHART.humidity }, { label: t('ghala.temperature'), color: CHART.temperature }, { label: t('ghala.safeLimit'), color: '#5e6a5f', dashed: true }]} />
                  <SimulatedTag label={t('ghala.sensorSimulated')} />
                </div>
              </>
            ) : (
              <EmptyState compact title={t('farm.noReadings')} />
            )}
            {data.risk.drivers.length > 0 && (
              <ul className="mt-3 space-y-1 text-[13px] text-ink-soft">
                {data.risk.drivers.map((d, i) => (
                  <li key={i}>· {bi(d)}</li>
                ))}
              </ul>
            )}
          </Card>

          {data.digital_ghala.length > 1 && (
            <Card title={t('market.digitalGhala')} subtitle={t('market.digitalGhalaSub', { farmer: data.farmer.display_name, warehouse: data.warehouse?.name })}>
              <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {data.digital_ghala.map((b: any) => (
                  <li key={b.batch_id} className={cx('rounded-md border p-3 text-sm', b.batch_id === data.batch_id ? 'border-forest-700 bg-forest-50' : 'border-line')}>
                    <div className="font-medium">
                      {t(`crops.${b.crop_type}`)} · {b.grade}
                    </div>
                    <div className="num text-[13px] text-muted">{f.kg(b.available_kg)}</div>
                    <div className="mt-1.5">
                      <RiskBadge level={b.risk} />
                    </div>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>

        <div className="space-y-5">
          <Card title={t('market.requestPurchase')}>
            <form onSubmit={submit} className="space-y-4" noValidate>
              <Field label={t('ghala.quantityKg')} error={qtyError} hint={t('market.availableHint', { kg: f.kg(data.available_kg) })}>
                <input className="input num" inputMode="decimal" value={qty} onChange={(e) => setQty(e.target.value)} aria-invalid={Boolean(qtyError)} placeholder={String(shares[0]?.kg ?? '')} />
              </Field>
              <div className="flex gap-2">
                {shares.map(({ share, kg }) => (
                  <button key={share} type="button" onClick={() => setQty(String(kg))} className="min-h-9 flex-1 rounded-md border border-line-strong text-[13px] hover:bg-sunken">
                    {share === 1 ? t('market.all') : `${share * 100}%`}
                  </button>
                ))}
              </div>
              <div className="flex items-baseline justify-between border-t border-line pt-3">
                <span className="text-sm text-muted">{t('market.total')}</span>
                <span className="num text-xl font-semibold">{f.tzs(total || 0)}</span>
              </div>
              <ErrorNote text={orderError} />
              <Button type="submit" size="lg" busy={busy} className="w-full" disabled={!qty}>
                {t('market.sendRequest')}
              </Button>
              <p className="text-xs text-muted">{t('market.requestNote')}</p>
            </form>
          </Card>

          <Card title={t('market.trust')}>
            <div className="flex items-start gap-4">
              <QrImage id={data.batch_id} />
              <div className="min-w-0 space-y-2 text-sm">
                <VerifyBadge status={data.verification_status} size="md" />
                <p className="text-[13px] text-muted">{t('market.trustBody', { count: data.verification.checks.length })}</p>
                <Link to={`/verify/${data.batch_id}`} className="inline-flex items-center gap-1.5 font-medium text-forest-800">
                  <ShieldCheck className="size-4" aria-hidden /> {t('market.seeJourney')}
                </Link>
              </div>
            </div>
          </Card>

          <Card title={t('market.supplier')}>
            <KeyValues
              cols={1}
              items={[
                [t('market.farmer'), `${data.farmer.display_name} · ${data.farmer.public_id}`],
                [t('auth.cooperative'), data.farmer.cooperative ?? '—'],
                [t('market.origin'), [data.farmer.district, data.farmer.region].filter(Boolean).join(', ')],
              ]}
            />
            <p className="mt-3 flex items-center gap-1.5 text-xs text-muted">
              <Warehouse className="size-3.5" aria-hidden /> {t('market.contactAfterAccept')}
            </p>
          </Card>
          <p className="flex items-center gap-1.5 text-xs text-muted">
            <Clock className="size-3.5" aria-hidden /> {t('market.priceSetBy')}
          </p>
        </div>
      </div>

      <ConfirmAction
        open={confirm}
        title={t('market.confirmTitle')}
        summary={[
          [t('market.product'), `${t(`crops.${data.crop_type}`)} · ${t('ghala.gradeX', { grade: data.grade })} · ${data.batch_id}`],
          [t('ghala.quantityKg'), f.kg(qtyNum)],
          [t('market.total'), f.tzs(total)],
          [t('market.supplier'), data.farmer.cooperative ?? data.farmer.display_name],
        ]}
        note={t('market.largeOrderNote')}
        confirmLabel={t('market.sendRequest')}
        onClose={() => setConfirm(false)}
        onConfirm={(pin) => place(pin)}
      />
    </div>
  )
}

