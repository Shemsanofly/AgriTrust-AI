import { ArrowRight, CalendarClock, Check, CloudRain, Droplets, FlaskRound, MapPin, Thermometer, Warehouse, type LucideIcon } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { AlertsPanel } from '../../components/AlertsPanel'
import { cropIcon } from '../../components/crops'
import { Badge, Card, EmptyState, ErrorState, Loading, ProgressBar, RiskBadge, Stat, StatStrip, cx } from '../../components/ui'
import { useAuth } from '../../lib/auth'
import { useApi, useBi, useErrorText, useFormat } from '../../lib/hooks'
import { IrrigationCard } from './IrrigationCard'
import { daysUntil, moistureState, seasonProgress, type Batch, type Farm, type Weather } from './shared'

type Order = { id: number; status: string; batch_id: string; quantity_kg: number; total: number; updated_at: string; buyer: { business_name: string } }

function greetingKey() {
  const h = new Date().getHours()
  return h < 12 ? 'home.morning' : h < 17 ? 'home.afternoon' : 'home.evening'
}

export function FarmerHome() {
  const { t } = useTranslation()
  const f = useFormat()
  const errorText = useErrorText()
  const { user } = useAuth()
  const [tick, setTick] = useState(0)
  const { data: farms, loading, error, reload } = useApi<Farm[]>('/farms', [tick])
  const { data: batches } = useApi<Batch[]>('/batches', [tick])
  const { data: orders } = useApi<Order[]>('/orders', [tick])
  const farm = farms?.find((x) => x.sensors.some((s) => s.type === 'soil')) ?? farms?.[0]
  const { data: weather } = useApi<Weather>(farm ? `/farms/${farm.id}/weather` : null, [tick])

  if (loading && !farms) return <Loading rows={4} />
  if (error) return <ErrorState text={errorText(error)} onRetry={reload} />
  if (!farm)
    return (
      <EmptyState
        title={t('home.noFarmTitle')}
        body={t('home.noFarmBody')}
        action={
          <Link to="/farm" className="inline-flex min-h-11 items-center rounded-md bg-forest-800 px-4 text-sm font-medium text-white">
            {t('farm.addFarm')}
          </Link>
        }
      />
    )

  const firstName = (user?.full_name ?? '').replace(/^Mama |^Baba /, '').split(' ')[0]
  const crop = farm.crops.find((c) => c.growth_stage !== 'harvested')
  const moisture = farm.latest.soil_moisture_pct
  const soilTemp = farm.latest.soil_temperature_c
  const state = moistureState(moisture?.value)
  const rain2 = weather ? weather.days.slice(0, 2).reduce((s, d) => s + d.rain_mm, 0) : null
  const today = weather?.days[0]

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm text-muted">{new Date().toLocaleDateString(f.locale, { weekday: 'long', day: 'numeric', month: 'long' })}</p>
          <h1 className="mt-0.5 text-[22px] font-semibold tracking-tight sm:text-2xl">{t(greetingKey(), { name: firstName })}</h1>
        </div>
        <p className="flex items-center gap-1.5 text-sm text-muted">
          <MapPin className="size-4" aria-hidden /> {farm.name}, {farm.region}
          {today && (
            <span className="ml-2 flex items-center gap-1">
              · {today.rain_mm >= 2 ? <CloudRain className="size-4" aria-hidden /> : <Thermometer className="size-4" aria-hidden />} {f.num(today.tmax_c)}°C
            </span>
          )}
        </p>
      </header>

      <SeasonJourney farms={farms ?? []} batches={batches ?? []} orders={orders ?? []} />

      <div className="grid gap-5 lg:grid-cols-[1.35fr_1fr]">
        <div className="space-y-5">
          <IrrigationCard farmId={farm.id} refreshKey={tick} onChanged={() => setTick((x) => x + 1)} />

          <StatStrip>
            <Stat
              icon={Droplets}
              label={t('farm.soilMoisture')}
              value={moisture ? `${f.num(moisture.value, 1)}%` : '—'}
              sub={state ? t(`farm.moisture.${state}`) : t('farm.noReadings')}
              tone={state === 'dry' ? 'amber' : undefined}
            />
            <Stat icon={Thermometer} label={t('farm.soilTemp')} value={soilTemp ? `${f.num(soilTemp.value, 1)}°C` : '—'} sub={moisture ? f.relative(moisture.ts) : undefined} />
            <Stat
              icon={FlaskRound}
              label={t('farm.soilPh')}
              value={farm.soil_ph != null ? f.num(farm.soil_ph, 1) : '—'}
              sub={farm.soil_ph != null ? t(`soilPh.${phBand(farm.soil_ph)}`) : t('farm.noSoilTest')}
            />
            <Stat icon={CloudRain} label={t('farm.rainNext2Days')} value={rain2 != null ? `${f.num(rain2, 1)} mm` : '—'} sub={weather?.simulated ? t('common.simulated') : 'Open-Meteo'} />
          </StatStrip>

          {crop && <CropStatus farm={farm} />}
        </div>

        <div className="space-y-5">
          <AlertsPanel refreshKey={tick} limit={3} title={t('home.needsAttention')} />
          <GhalaSnapshot batches={batches ?? []} />
          <RecentActivity batches={batches ?? []} orders={orders ?? []} />
        </div>
      </div>
    </div>
  )
}

function phBand(ph: number) {
  return ph < 5.5 ? 'acidic' : ph < 6.6 ? 'slightly_acidic' : ph <= 7.3 ? 'neutral' : 'alkaline'
}

function CropStatus({ farm }: { farm: Farm }) {
  const { t } = useTranslation()
  const f = useFormat()
  const crop = farm.crops.find((c) => c.growth_stage !== 'harvested')!
  const Icon = cropIcon(crop.crop_type)
  const progress = seasonProgress(crop)
  const days = daysUntil(crop.expected_harvest_date)
  return (
    <Card title={t('home.cropStatus')} actions={<Link to="/farm" className="text-sm font-medium text-forest-800">{t('home.openFarm')}</Link>}>
      <div className="flex items-center gap-3">
        <span className="flex size-10 items-center justify-center rounded-md bg-harvest-100 text-harvest-800">
          <Icon className="size-5" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <div className="font-semibold">
            {t(`crops.${crop.crop_type}`)} {crop.variety && <span className="font-normal text-muted">· {crop.variety}</span>}
          </div>
          <div className="text-[13px] text-muted">
            {t('home.stageNow', { stage: t(`stages.${crop.growth_stage}`) })} · {farm.name}
          </div>
        </div>
        <div className="text-right">
          <div className="num text-sm font-semibold">{days != null ? (days <= 0 ? t('farm.harvestDue') : t('farm.daysLeft', { count: days })) : '—'}</div>
          <div className="text-xs text-muted">{t('farm.expectedHarvest')}</div>
        </div>
      </div>
      {progress != null && (
        <div className="mt-4">
          <ProgressBar value={progress} label={t('farm.seasonProgress', { pct: progress })} />
          <div className="mt-1.5 flex justify-between text-xs text-muted">
            <span>{f.date(crop.planting_date)}</span>
            <span>{t('farm.seasonProgress', { pct: progress })}</span>
            <span>{f.date(crop.expected_harvest_date)}</span>
          </div>
        </div>
      )}
    </Card>
  )
}

/** Where the farmer is in the season (Shambani → Kifedha) and what to do next. */
function SeasonJourney({ farms, batches, orders }: { farms: Farm[]; batches: Batch[]; orders: Order[] }) {
  const { t } = useTranslation()
  const readyCrop = farms.flatMap((x) => x.crops).find((c) => c.growth_stage === 'maturity')
  const harvested = batches.find((b) => b.status === 'HARVESTED')
  const stored = batches.filter((b) => b.status === 'IN_STORAGE')
  const unlisted = stored.find((b) => !b.listed)
  const pendingOrder = orders.find((o) => ['REQUESTED', 'DELIVERED'].includes(o.status))
  const sold = orders.some((o) => o.status === 'SALE_CONFIRMED')

  const steps: { key: string; done: boolean }[] = [
    { key: 'shambani', done: farms.length > 0 },
    { key: 'mavuno', done: batches.length > 0 },
    { key: 'ghalani', done: stored.length > 0 },
    { key: 'sokoni', done: sold || stored.some((b) => b.listed) },
    { key: 'kifedha', done: sold },
  ]

  let next: { text: string; to: string } | null = null
  if (pendingOrder) next = { text: pendingOrder.status === 'REQUESTED' ? t('journey.next.order') : t('journey.next.confirmSale'), to: '/market' }
  else if (readyCrop) next = { text: t('journey.next.harvest', { crop: t(`crops.${readyCrop.crop_type}`) }), to: '/ghala?harvest=1' }
  else if (harvested) next = { text: t('journey.next.deliver', { batch: harvested.id }), to: `/ghala/${harvested.id}` }
  else if (unlisted) next = { text: t('journey.next.list', { batch: unlisted.id }), to: `/ghala/${unlisted.id}` }
  else if (sold) next = { text: t('journey.next.finance'), to: '/finance' }

  return (
    <section className="rounded-(--radius-card) border border-line bg-surface p-4 sm:p-5" aria-label={t('journey.title')}>
      <ol className="grid grid-cols-5 gap-1.5 sm:gap-3">
        {steps.map((s, i) => (
          <li key={s.key} className="min-w-0">
            <div className={cx('h-1 rounded-full', s.done ? 'bg-forest-700' : 'bg-line')} />
            <div className={cx('mt-2 flex items-center gap-1 text-[11px] sm:text-xs', s.done ? 'font-semibold text-ink' : 'text-muted')}>
              {s.done && <Check className="size-3 shrink-0 text-forest-700" aria-hidden />}
              <span className="truncate">
                <span className="hidden sm:inline">{i + 1}. </span>
                {t(`journey.${s.key}`)}
              </span>
            </div>
          </li>
        ))}
      </ol>
      {next && (
        <Link to={next.to} className="mt-4 flex items-center justify-between gap-3 rounded-md bg-harvest-100 px-3.5 py-3 text-sm font-medium text-harvest-800 hover:bg-harvest-200">
          <span>
            <span className="mr-1.5 font-semibold">{t('journey.nextStep')}:</span>
            {next.text}
          </span>
          <ArrowRight className="size-4 shrink-0" aria-hidden />
        </Link>
      )}
    </section>
  )
}

function GhalaSnapshot({ batches }: { batches: Batch[] }) {
  const { t } = useTranslation()
  const bi = useBi()
  const f = useFormat()
  const stored = batches.filter((b) => b.status === 'IN_STORAGE')
  return (
    <Card title={t('home.inGhala')} actions={<Link to="/ghala" className="text-sm font-medium text-forest-800">{t('common.viewAll')}</Link>}>
      {!stored.length ? (
        <EmptyState compact icon={Warehouse} title={t('ghala.nothingStored')} />
      ) : (
        <ul className="-my-2 divide-y divide-line">
          {stored.map((b) => (
            <li key={b.id}>
              <Link to={`/ghala/${b.id}`} className="flex items-center gap-3 py-2.5">
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium">
                    {t(`crops.${b.crop_type}`)} · {f.kg(b.available_kg)}
                  </div>
                  <div className="truncate text-xs text-muted">{b.risk?.level === 'HIGH' ? bi(b.risk.headline) : `${b.warehouse?.name} · ${t('ghala.daysStored', { count: b.days_in_storage ?? 0 })}`}</div>
                </div>
                <RiskBadge level={b.risk?.level} />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

function RecentActivity({ batches, orders }: { batches: Batch[]; orders: Order[] }) {
  const { t } = useTranslation()
  const f = useFormat()
  const events: { at: string; icon: LucideIcon; text: string }[] = []
  for (const b of batches) {
    events.push({ at: b.created_at, icon: cropIcon(b.crop_type), text: t('activity.batch', { batch: b.id, kg: f.kg(b.quantity_kg) }) })
    if (b.receipt) events.push({ at: b.receipt.created_at, icon: Warehouse, text: t('activity.receipt', { receipt: b.receipt.id }) })
  }
  for (const o of orders) events.push({ at: o.updated_at, icon: CalendarClock, text: t('activity.order', { buyer: o.buyer.business_name, status: t(`status.${o.status}`) }) })
  events.sort((a, b) => b.at.localeCompare(a.at))
  return (
    <Card title={t('home.recentActivity')}>
      {!events.length ? (
        <EmptyState compact title={t('activity.none')} />
      ) : (
        <ol className="space-y-3">
          {events.slice(0, 5).map((e, i) => (
            <li key={i} className="flex gap-3 text-sm">
              <e.icon className="mt-0.5 size-4 shrink-0 text-muted" aria-hidden />
              <div className="min-w-0 flex-1">
                <p className="text-ink">{e.text}</p>
                <p className="text-xs text-muted">{f.relative(e.at)}</p>
              </div>
            </li>
          ))}
        </ol>
      )}
      {events.length > 0 && <Badge className="mt-3" tone="stone">{t('activity.verifiedNote')}</Badge>}
    </Card>
  )
}
