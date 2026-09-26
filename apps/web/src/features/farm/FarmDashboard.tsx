import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { AlertsPanel } from '../../components/AlertsPanel'
import { TimeSeriesChart, pivotReadings } from '../../components/Charts'
import { Badge, Button, Card, Empty, ErrorNote, Field, Loading, SimulatedTag, Tabs } from '../../components/ui'
import { api } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { useApi, useBi, useErrorText, useFormat, type Bi } from '../../lib/hooks'

type Crop = {
  id: number
  crop_type: string
  variety?: string
  growth_stage: string
  planting_date: string
  expected_harvest_date?: string
}

type Farm = {
  id: number
  name: string
  region: string
  lat: number
  lon: number
  acreage: number
  soil_type: string
  irrigation_type: string
  created_at?: string
  crops: Crop[]
  sensors: { device_id: string; type: string; simulated: boolean; last_seen_at: string | null }[]
  latest: Record<string, { value: number; ts: string; quality_flag: string }>
}

type PlantingAdvice = {
  headline: Bi
  soil_summary: Bi
  tips: Bi[]
  recommendations: {
    crop_type: string
    fit: 'excellent' | 'good' | 'fair' | 'poor'
    fit_label: Bi
    name: Bi
    reason: Bi
  }[]
  current_crop: {
    crop_type: string
    fit: 'excellent' | 'good' | 'fair' | 'poor'
    fit_label: Bi
    name: Bi
    note: Bi
  } | null
  model_version: string
}

const STAGES = ['initial', 'vegetative', 'flowering', 'maturity'] as const

const CROP_ICON: Record<string, string> = {
  maize: '🌽',
  beans: '🫘',
  rice: '🌾',
  sorghum: '🌿',
  sunflower: '🌻',
}

/** Ideal volumetric soil moisture band used for the Dry / Good / Wet status. */
const MOISTURE_IDEAL = { min: 25, max: 55 }
const DAY_MS = 86_400_000

const FIT_TONE: Record<string, 'green' | 'blue' | 'amber' | 'red'> = {
  excellent: 'green',
  good: 'blue',
  fair: 'amber',
  poor: 'red',
}

const FIT_BORDER: Record<string, string> = {
  excellent: 'border-l-green-500',
  good: 'border-l-sky-500',
  fair: 'border-l-amber-500',
  poor: 'border-l-red-500',
}

type Weather = { simulated: boolean; source: string; days: { date: string; rain_mm: number; et0_mm: number; tmax_c: number }[] }

const weatherIcon = (d: { rain_mm: number; tmax_c: number }) => (d.rain_mm >= 2 ? '🌧️' : d.tmax_c >= 30 ? '☀️' : '⛅')
const clamp = (n: number, lo = 0, hi = 100) => Math.min(hi, Math.max(lo, n))

/** Share of the season elapsed between planting and expected harvest (0–100), or null if unknown. */
function seasonProgress(c: Crop) {
  if (c.growth_stage === 'harvested') return 100
  if (!c.expected_harvest_date) return null
  const start = new Date(c.planting_date).getTime()
  const end = new Date(c.expected_harvest_date).getTime()
  if (!(end > start)) return null
  return Math.round(clamp(((Date.now() - start) / (end - start)) * 100))
}

export function FarmDashboard() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const { data: farms, loading, reload: reloadFarms } = useApi<Farm[]>('/farms')
  const [farmId, setFarmId] = useState<number | null>(null)
  const [showAdd, setShowAdd] = useState(false)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    if (farms?.length && !farms.some((f) => f.id === farmId)) setFarmId(farms[0].id)
  }, [farms, farmId])

  if (loading && !farms) return <Loading />
  const farm = farms?.find((f) => f.id === farmId)

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold tracking-tight text-stone-900">
            {user ? t('farm.welcome', { name: user.full_name.split(' ')[0] }) : t('farm.title')}
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-stone-600">{t('farm.welcomeSub')}</p>
        </div>
        <Button variant={showAdd ? 'secondary' : 'primary'} onClick={() => setShowAdd((v) => !v)}>
          {showAdd ? t('common.close') : `+ ${t('farm.addFarm')}`}
        </Button>
      </div>

      {showAdd && (
        <AddFarm
          onDone={() => {
            setShowAdd(false)
            reloadFarms()
          }}
        />
      )}

      {farms && farms.length > 1 && (
        <Tabs tabs={farms.map((f) => ({ id: String(f.id), label: f.name }))} value={String(farmId)} onChange={(id) => setFarmId(Number(id))} />
      )}

      {farm ? (
        <FarmView key={`${farm.id}-${tick}`} farm={farm} onChanged={() => (reloadFarms(), setTick((x) => x + 1))} />
      ) : (
        <>
          {!farms?.length && <Empty>{t('farm.noFarms')}</Empty>}
          <AlertsPanel refreshKey={tick} />
        </>
      )}
    </div>
  )
}

function FarmView({ farm, onChanged }: { farm: Farm; onChanged: () => void }) {
  const { t } = useTranslation()
  const bi = useBi()
  const f = useFormat()
  const errorText = useErrorText()
  const soilSensor = farm.sensors.find((s) => s.type === 'soil')
  const { data: planting, error: plantingError } = useApi<PlantingAdvice>(`/farms/${farm.id}/planting-advice`)
  const { data: readings } = useApi<{ ts: string; metric: string; value: number }[]>(`/farms/${farm.id}/readings?hours=48`)
  const { data: weather } = useApi<Weather>(`/farms/${farm.id}/weather`)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const run = async (key: string, fn: () => Promise<unknown>) => {
    setBusy(key)
    setError(null)
    try {
      await fn()
      onChanged()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(null)
    }
  }

  const moisture = farm.latest.soil_moisture_pct
  const soilTemp = farm.latest.soil_temperature_c
  const today = weather?.days?.[0]
  const rain7 = weather?.days.reduce((sum, d) => sum + d.rain_mm, 0)
  const rainyDays = weather?.days.filter((d) => d.rain_mm >= 2).length ?? 0
  const nextHarvest = farm.crops
    .filter((c) => c.growth_stage !== 'harvested' && c.expected_harvest_date)
    .map((c) => ({ crop: c, days: Math.ceil((new Date(c.expected_harvest_date!).getTime() - Date.now()) / DAY_MS) }))
    .sort((a, b) => a.days - b.days)[0]
  const pivoted = readings?.length ? pivotReadings(readings) : null

  const moistureStatus = !moisture
    ? null
    : moisture.value < MOISTURE_IDEAL.min
      ? { label: t('farm.statusDry'), tone: 'amber' as const }
      : moisture.value > MOISTURE_IDEAL.max
        ? { label: t('farm.statusWet'), tone: 'blue' as const }
        : { label: t('farm.statusGood'), tone: 'green' as const }

  return (
    <div className="space-y-5">
      {/* Hero: identity, registration summary and today's weather */}
      <section className="relative overflow-hidden rounded-3xl bg-linear-to-br from-brand-900 via-brand-800 to-brand-700 p-5 text-white shadow-lg sm:p-7">
        <FieldPattern className="pointer-events-none absolute -right-16 -bottom-12 h-72 w-[28rem] text-white/10" />
        <div className="relative flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-semibold tracking-widest text-brand-200 uppercase">📍 {farm.region}</p>
            <h2 className="mt-1 truncate text-2xl font-bold tracking-tight sm:text-3xl">{farm.name}</h2>
            <div className="mt-4 flex flex-wrap gap-2">
              <HeroChip icon="📐">
                {f.num(farm.acreage, 1)} {t('farm.acres')}
              </HeroChip>
              <HeroChip icon="🟫">{t(`soil.${farm.soil_type}`, { defaultValue: farm.soil_type })}</HeroChip>
              <HeroChip icon="💧">{t(`irrigation.${farm.irrigation_type}`, { defaultValue: farm.irrigation_type })}</HeroChip>
              <HeroChip icon="🌱">{t('farm.cropsCount', { count: farm.crops.length })}</HeroChip>
            </div>
            <p className="mt-4 font-mono text-[11px] text-white/60">
              {f.num(farm.lat, 4)}, {f.num(farm.lon, 4)}
              {farm.created_at ? ` · ${t('farm.registered')} ${f.date(farm.created_at)}` : ''}
            </p>
          </div>
          {today && (
            <div className="flex shrink-0 items-center gap-4 rounded-2xl bg-white/10 px-5 py-4 ring-1 ring-white/20 backdrop-blur-sm">
              <span className="text-4xl" aria-hidden>
                {weatherIcon(today)}
              </span>
              <div>
                <div className="text-xs font-medium text-white/70">{t('farm.weatherToday')}</div>
                <div className="text-3xl leading-tight font-semibold">{f.num(today.tmax_c)}°C</div>
                <div className="flex items-center gap-2 text-xs text-white/80">
                  {f.num(today.rain_mm, 1)} mm
                  {weather?.simulated && <SimulatedTag />}
                </div>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Headline numbers */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi
          icon="💧"
          iconBg="bg-sky-50"
          label={t('farm.soilMoisture')}
          value={moisture ? `${f.num(moisture.value, 1)}%` : '—'}
          meta={moisture ? f.dateTime(moisture.ts) : t('farm.noReadings')}
          status={moistureStatus?.label}
          statusTone={moistureStatus?.tone}
        >
          <RangeBar
            value={moisture?.value ?? null}
            min={0}
            max={100}
            band={[MOISTURE_IDEAL.min, MOISTURE_IDEAL.max]}
            color="#0284c7"
            caption={t('farm.idealRange', { min: MOISTURE_IDEAL.min, max: MOISTURE_IDEAL.max })}
          />
        </Kpi>
        <Kpi
          icon="🌡️"
          iconBg="bg-orange-50"
          label={t('farm.soilTemp')}
          value={soilTemp ? `${f.num(soilTemp.value, 1)}°C` : '—'}
          meta={soilSensor?.simulated ? t('common.simulated') : t('farm.liveFromSensor')}
          status={soilTemp ? t('farm.statusNormal') : t('farm.statusUnknown')}
          statusTone={soilTemp ? 'green' : 'stone'}
        >
          <RangeBar value={soilTemp?.value ?? null} min={10} max={40} color="#c2410c" caption="10–40°C" />
        </Kpi>
        <Kpi
          icon="🌧️"
          iconBg="bg-indigo-50"
          label={t('farm.rain7d')}
          value={rain7 != null ? `${f.num(rain7, 1)} mm` : '—'}
          meta={weather ? t('farm.rainyDays', { count: rainyDays }) : t('common.loading')}
        />
        <Kpi
          icon="🧺"
          iconBg="bg-amber-50"
          label={t('farm.nextHarvest')}
          value={nextHarvest ? f.date(nextHarvest.crop.expected_harvest_date) : '—'}
          meta={
            nextHarvest
              ? `${t(`crops.${nextHarvest.crop.crop_type}`, { defaultValue: nextHarvest.crop.crop_type })} · ${
                  nextHarvest.days <= 0 ? t('farm.harvestDue') : t('farm.daysLeft', { count: nextHarvest.days })
                }`
              : t('farm.noHarvestDate')
          }
          valueClass="text-xl sm:text-2xl"
        />
      </div>

      {/* Main body: monitoring on the left, context on the right */}
      <div className="grid gap-5 lg:grid-cols-3">
        <div className="space-y-5 lg:col-span-2">
          <Card
            title={t('farm.readings48h')}
            actions={
              <div className="flex flex-wrap items-center gap-1.5">
                {soilSensor?.simulated && <SimulatedTag />}
                <Button variant="ghost" className="min-h-8 px-2 text-xs" busy={busy === 'dry'} onClick={() => run('dry', () => api('/demo/scenario/soil-drying', { method: 'POST' }))}>
                  🌵 {t('farm.demoDry')}
                </Button>
                <Button variant="ghost" className="min-h-8 px-2 text-xs" busy={busy === 'wet'} onClick={() => run('wet', () => api('/demo/scenario/soil-wet', { method: 'POST' }))}>
                  🌧️ {t('farm.demoWet')}
                </Button>
              </div>
            }
          >
            <ErrorNote text={error} />
            {pivoted ? (
              <div className="grid gap-4">
                <ChartBlock label={t('farm.soilMoisture')} value={moisture ? `${f.num(moisture.value, 1)}%` : '—'} color="#0284c7">
                  <TimeSeriesChart
                    height={170}
                    data={pivoted}
                    band={{ from: MOISTURE_IDEAL.min, to: MOISTURE_IDEAL.max, color: '#16a34a' }}
                    series={[{ key: 'soil_moisture_pct', label: t('farm.soilMoisture'), unit: '%', color: '#0284c7' }]}
                  />
                </ChartBlock>
                <ChartBlock label={t('farm.soilTemp')} value={soilTemp ? `${f.num(soilTemp.value, 1)}°C` : '—'} color="#c2410c">
                  <TimeSeriesChart
                    height={150}
                    data={pivoted}
                    series={[{ key: 'soil_temperature_c', label: t('farm.soilTemp'), unit: '°C', color: '#c2410c' }]}
                  />
                </ChartBlock>
              </div>
            ) : (
              <Empty>{soilSensor ? t('farm.noReadings') : t('farm.noSensor')}</Empty>
            )}
          </Card>

          <Card title={t('farm.cropsTitle')} actions={<Badge tone="green">{t('farm.cropsCount', { count: farm.crops.length })}</Badge>}>
            {!farm.crops.length ? (
              <Empty>{t('farm.noCrops')}</Empty>
            ) : (
              <ul className="space-y-3">
                {farm.crops.map((c) => {
                  const fit = planting?.recommendations.find((r) => r.crop_type === c.crop_type)
                  const progress = seasonProgress(c)
                  const stageIdx = STAGES.indexOf(c.growth_stage as (typeof STAGES)[number])
                  return (
                    <li key={c.id} className="rounded-2xl border border-stone-200 bg-stone-50/50 p-4">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="flex min-w-0 items-center gap-3">
                          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-white text-xl shadow-sm ring-1 ring-stone-200" aria-hidden>
                            {CROP_ICON[c.crop_type] ?? '🌱'}
                          </span>
                          <div className="min-w-0">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="font-semibold text-stone-900">{t(`crops.${c.crop_type}`, { defaultValue: c.crop_type })}</span>
                              {c.variety && <span className="text-xs text-stone-500">{c.variety}</span>}
                              {fit && <Badge tone={FIT_TONE[fit.fit]}>{bi(fit.fit_label)}</Badge>}
                            </div>
                            <p className="mt-0.5 text-xs text-stone-500">
                              {t('farm.planted')} {f.date(c.planting_date)}
                              {c.expected_harvest_date ? ` → ${t('farm.expectedHarvest')} ${f.date(c.expected_harvest_date)}` : ''}
                            </p>
                          </div>
                        </div>
                        {c.growth_stage === 'harvested' && <Badge tone="stone">{t('stages.harvested')}</Badge>}
                      </div>

                      {progress != null && (
                        <div className="mt-3">
                          <div className="mb-1 flex justify-end text-[11px] font-medium text-stone-500">{t('farm.seasonProgress', { pct: progress })}</div>
                          <div className="h-1.5 overflow-hidden rounded-full bg-stone-200">
                            <div className="h-full rounded-full bg-brand-600 transition-all" style={{ width: `${progress}%` }} />
                          </div>
                        </div>
                      )}

                      {c.growth_stage !== 'harvested' && (
                        <ol className="mt-4 grid grid-cols-4" aria-label={t('farm.cropStage')}>
                          {STAGES.map((stage, i) => {
                            const current = i === stageIdx
                            const done = i < stageIdx
                            return (
                              <li key={stage}>
                                <button
                                  type="button"
                                  aria-pressed={current}
                                  disabled={busy === `stage-${c.id}-${stage}`}
                                  onClick={() => run(`stage-${c.id}-${stage}`, () => api(`/crops/${c.id}`, { method: 'PATCH', body: { growth_stage: stage } }))}
                                  className="group flex w-full flex-col items-center gap-1.5 disabled:opacity-60"
                                >
                                  <span className="flex w-full items-center">
                                    <span className={`h-0.5 flex-1 ${i === 0 ? 'invisible' : i <= stageIdx ? 'bg-brand-600' : 'bg-stone-200'}`} />
                                    <span
                                      className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold transition ${
                                        current
                                          ? 'bg-brand-700 text-white ring-4 ring-brand-100'
                                          : done
                                            ? 'bg-brand-600 text-white'
                                            : 'border-2 border-stone-300 bg-white text-stone-400 group-hover:border-brand-600 group-hover:text-brand-700'
                                      }`}
                                    >
                                      {done ? '✓' : i + 1}
                                    </span>
                                    <span className={`h-0.5 flex-1 ${i === STAGES.length - 1 ? 'invisible' : i < stageIdx ? 'bg-brand-600' : 'bg-stone-200'}`} />
                                  </span>
                                  <span className={`text-[11px] leading-tight font-medium ${current ? 'text-brand-800' : 'text-stone-500'}`}>{t(`stages.${stage}`)}</span>
                                </button>
                              </li>
                            )
                          })}
                        </ol>
                      )}
                    </li>
                  )
                })}
              </ul>
            )}
          </Card>
        </div>

        <aside className="space-y-5">
          <AlertsPanel limit={4} />

          {weather && (
            <Card title={t('farm.weather')} actions={weather.simulated ? <SimulatedTag /> : <Badge tone="blue">Open-Meteo</Badge>}>
              <ul className="divide-y divide-stone-100">
                {weather.days.map((d, i) => {
                  const maxRain = Math.max(1, ...weather.days.map((x) => x.rain_mm))
                  return (
                    <li key={d.date} className="grid grid-cols-[4.75rem_1.75rem_1fr_2.5rem] items-center gap-2 py-2 text-sm">
                      <span className={`truncate font-medium ${i === 0 ? 'text-brand-800' : 'text-stone-600'}`}>{i === 0 ? t('farm.today') : f.weekday(d.date)}</span>
                      <span className="text-lg" aria-hidden>
                        {weatherIcon(d)}
                      </span>
                      <span className="flex min-w-0 items-center gap-2" title={`${f.num(d.rain_mm, 1)} mm`}>
                        <span className="h-2 flex-1 overflow-hidden rounded-full bg-stone-100">
                          <span className="block h-full rounded-full bg-sky-500" style={{ width: `${d.rain_mm > 0 ? Math.max(4, (d.rain_mm / maxRain) * 100) : 0}%` }} />
                        </span>
                        <span className="w-12 text-right text-xs text-stone-500 tabular-nums">{f.num(d.rain_mm, 1)} mm</span>
                      </span>
                      <span className="text-right font-semibold text-stone-900 tabular-nums">{f.num(d.tmax_c)}°</span>
                    </li>
                  )
                })}
              </ul>
            </Card>
          )}

          <Card title={t('farm.sensors')}>
            {!farm.sensors.length ? (
              <Empty>{t('farm.noSensor')}</Empty>
            ) : (
              <ul className="space-y-2">
                {farm.sensors.map((s) => {
                  const online = !!s.last_seen_at && Date.now() - new Date(s.last_seen_at).getTime() < 2 * 3_600_000
                  return (
                    <li key={s.device_id} className="flex items-center gap-3 rounded-xl bg-stone-50 px-3 py-2.5">
                      <span className="relative flex h-2.5 w-2.5 shrink-0">
                        {online && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-60" />}
                        <span className={`relative inline-flex h-2.5 w-2.5 rounded-full ${online ? 'bg-green-500' : 'bg-stone-300'}`} />
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="truncate font-mono text-xs font-medium text-stone-800">{s.device_id}</div>
                        <div className="text-[11px] text-stone-500">
                          {online ? t('farm.sensorOnline') : t('farm.sensorOffline')} ·{' '}
                          {s.last_seen_at ? t('farm.lastSeen', { time: f.dateTime(s.last_seen_at) }) : t('farm.neverSeen')}
                        </div>
                      </div>
                      {s.simulated && <SimulatedTag />}
                    </li>
                  )
                })}
              </ul>
            )}
          </Card>
        </aside>
      </div>

      {/* Planting advice from soil type */}
      <Card
        title={
          <div>
            <div>🧭 {t('farm.advice')}</div>
            <p className="mt-0.5 text-xs font-normal text-stone-500">{t('farm.adviceSub')}</p>
          </div>
        }
        actions={<Badge tone="blue">{t('farm.rulesModel')}</Badge>}
      >
        {plantingError ? (
          <ErrorNote text={errorText(plantingError)} />
        ) : !planting ? (
          <Loading />
        ) : (
          <div className="space-y-5">
            <div className="flex flex-col gap-3 rounded-2xl bg-linear-to-r from-brand-50 to-emerald-50 p-4 ring-1 ring-brand-100 sm:flex-row sm:items-center">
              <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-white text-2xl shadow-sm" aria-hidden>
                🟫
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-lg font-semibold text-stone-900">{bi(planting.headline)}</p>
                <p className="mt-0.5 text-sm text-stone-600">{bi(planting.soil_summary)}</p>
              </div>
            </div>

            {planting.current_crop && (
              <div className={`flex flex-wrap items-start gap-2 rounded-xl border border-l-4 border-stone-200 bg-white px-4 py-3 ${FIT_BORDER[planting.current_crop.fit]}`}>
                <Badge tone={FIT_TONE[planting.current_crop.fit]}>{bi(planting.current_crop.fit_label)}</Badge>
                <div className="min-w-0 flex-1 text-sm text-stone-700">
                  <span className="font-medium text-stone-800">{t('farm.currentCropFit')}: </span>
                  {bi(planting.current_crop.note)}
                </div>
              </div>
            )}

            <div className="grid gap-5 lg:grid-cols-3">
              <div className="lg:col-span-2">
                <SectionLabel>{t('farm.recommendedCrops')}</SectionLabel>
                <ul className="grid gap-3 sm:grid-cols-2">
                  {planting.recommendations.map((rec) => (
                    <li key={rec.crop_type} className={`flex gap-3 rounded-xl border border-l-4 border-stone-200 bg-white p-3 shadow-sm ${FIT_BORDER[rec.fit]}`}>
                      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-stone-50 text-lg" aria-hidden>
                        {CROP_ICON[rec.crop_type] ?? '🌱'}
                      </span>
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-semibold text-stone-900">{bi(rec.name)}</span>
                          <Badge tone={FIT_TONE[rec.fit]}>{bi(rec.fit_label)}</Badge>
                        </div>
                        <p className="mt-1 text-xs leading-relaxed text-stone-600">{bi(rec.reason)}</p>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <SectionLabel>{t('farm.plantingTips')}</SectionLabel>
                <ol className="space-y-2.5 rounded-xl bg-stone-50 p-4 text-sm text-stone-700">
                  {planting.tips.map((tip, i) => (
                    <li key={i} className="flex gap-3">
                      <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-brand-700 text-[10px] font-bold text-white">{i + 1}</span>
                      <span>{bi(tip)}</span>
                    </li>
                  ))}
                </ol>
              </div>
            </div>

            <p className="text-[11px] text-stone-400">{planting.model_version}</p>
          </div>
        )}
      </Card>
    </div>
  )
}

function Kpi({
  icon,
  iconBg,
  label,
  value,
  meta,
  status,
  statusTone,
  valueClass = 'text-2xl sm:text-3xl',
  children,
}: {
  icon: string
  iconBg: string
  label: string
  value: string
  meta: string
  status?: string
  statusTone?: 'green' | 'amber' | 'blue' | 'stone'
  valueClass?: string
  children?: ReactNode
}) {
  return (
    <div className="flex flex-col rounded-2xl border border-stone-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <span className={`flex h-9 w-9 items-center justify-center rounded-xl text-lg ${iconBg}`} aria-hidden>
          {icon}
        </span>
        {status && statusTone && <Badge tone={statusTone}>{status}</Badge>}
      </div>
      <div className="mt-3 text-xs font-medium tracking-wide text-stone-500 uppercase">{label}</div>
      <div className={`mt-0.5 font-semibold tracking-tight text-stone-900 tabular-nums ${valueClass}`}>{value}</div>
      <div className="mt-0.5 truncate text-xs text-stone-500">{meta}</div>
      {children && <div className="mt-auto pt-3">{children}</div>}
    </div>
  )
}

/** Horizontal gauge with an optional shaded target band and a marker at the current value. */
function RangeBar({ value, min, max, band, color, caption }: { value: number | null; min: number; max: number; band?: [number, number]; color: string; caption?: string }) {
  const pct = (v: number) => clamp(((v - min) / (max - min)) * 100)
  return (
    <div>
      <div className="relative h-2 rounded-full bg-stone-100">
        {band && <div className="absolute inset-y-0 rounded-full bg-green-200" style={{ left: `${pct(band[0])}%`, width: `${pct(band[1]) - pct(band[0])}%` }} />}
        {value != null && (
          <div
            className="absolute top-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white shadow ring-1 ring-black/5 transition-all"
            style={{ left: `${pct(value)}%`, backgroundColor: color }}
          />
        )}
      </div>
      {caption && <div className="mt-1.5 text-[11px] text-stone-400">{caption}</div>}
    </div>
  )
}

function ChartBlock({ label, value, color, children }: { label: string; value: string; color: string; children: ReactNode }) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between gap-2">
        <span className="flex items-center gap-2 text-sm font-medium text-stone-700">
          <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} aria-hidden />
          {label}
        </span>
        <span className="text-sm font-semibold text-stone-900 tabular-nums">{value}</span>
      </div>
      {children}
    </div>
  )
}

function HeroChip({ icon, children }: { icon: string; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-white/10 px-3 py-1 text-xs font-medium ring-1 ring-white/15">
      <span aria-hidden>{icon}</span>
      {children}
    </span>
  )
}

function SectionLabel({ children }: { children: ReactNode }) {
  return <h3 className="mb-2 text-xs font-semibold tracking-wide text-stone-500 uppercase">{children}</h3>
}

/** Decorative contour lines suggesting ploughed field rows. */
function FieldPattern({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 440 280" fill="none" stroke="currentColor" strokeWidth="2" className={className} aria-hidden>
      {Array.from({ length: 10 }, (_, i) => (
        <path key={i} d={`M0 ${70 + i * 22} Q220 ${10 + i * 22} 440 ${70 + i * 22}`} />
      ))}
      <circle cx="360" cy="48" r="26" />
    </svg>
  )
}

function AddFarm({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const [form, setForm] = useState({
    name: '',
    region: '',
    lat: '',
    lon: '',
    acreage: '',
    soil_type: 'loam',
    irrigation_type: 'drip',
    crop_type: 'maize',
    planting_date: new Date().toISOString().slice(0, 10),
    expected_harvest_date: '',
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value })

  const useGps = () =>
    navigator.geolocation?.getCurrentPosition((pos) =>
      setForm((f) => ({ ...f, lat: pos.coords.latitude.toFixed(5), lon: pos.coords.longitude.toFixed(5) })),
    )

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api('/farms', {
        method: 'POST',
        body: {
          name: form.name,
          region: form.region,
          lat: Number(form.lat),
          lon: Number(form.lon),
          acreage: Number(form.acreage),
          soil_type: form.soil_type,
          irrigation_type: form.irrigation_type,
          crop: { crop_type: form.crop_type, planting_date: form.planting_date, expected_harvest_date: form.expected_harvest_date || null, growth_stage: 'initial' },
        },
      })
      onDone()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card title={t('farm.addFarm')}>
      <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2">
        <Field label={t('farm.name')}>
          <input className="input" value={form.name} onChange={set('name')} required />
        </Field>
        <Field label={t('auth.region')}>
          <input className="input" value={form.region} onChange={set('region')} required />
        </Field>
        <Field label={t('farm.location')} hint={<button type="button" className="text-brand-800 underline" onClick={useGps}>📍 {t('farm.useGps')}</button>}>
          <div className="flex gap-2">
            <input className="input" placeholder="lat" value={form.lat} onChange={set('lat')} required inputMode="decimal" />
            <input className="input" placeholder="lon" value={form.lon} onChange={set('lon')} required inputMode="decimal" />
          </div>
        </Field>
        <Field label={`${t('farm.acreage')} (${t('farm.acres')})`}>
          <input className="input" value={form.acreage} onChange={set('acreage')} required inputMode="decimal" />
        </Field>
        <Field label={t('farm.soilType')}>
          <select className="input" value={form.soil_type} onChange={set('soil_type')}>
            {['loam', 'sandy loam', 'clay', 'sandy'].map((s) => (
              <option key={s} value={s}>{t(`soil.${s}`)}</option>
            ))}
          </select>
        </Field>
        <Field label={t('farm.irrigationType')}>
          <select className="input" value={form.irrigation_type} onChange={set('irrigation_type')}>
            {['drip', 'furrow', 'sprinkler', 'rainfed'].map((s) => (
              <option key={s} value={s}>{t(`irrigation.${s}`)}</option>
            ))}
          </select>
        </Field>
        <Field label={t('farm.crop')}>
          <select className="input" value={form.crop_type} onChange={set('crop_type')}>
            {['maize', 'beans', 'rice', 'sorghum', 'sunflower'].map((c) => (
              <option key={c} value={c}>{t(`crops.${c}`)}</option>
            ))}
          </select>
        </Field>
        <Field label={t('farm.planted')}>
          <input className="input" type="date" value={form.planting_date} onChange={set('planting_date')} required />
        </Field>
        <Field label={t('farm.expectedHarvest')}>
          <input className="input" type="date" value={form.expected_harvest_date} onChange={set('expected_harvest_date')} />
        </Field>
        <div className="sm:col-span-2">
          <ErrorNote text={error} />
          <Button type="submit" busy={busy} className="mt-2">
            {t('common.save')}
          </Button>
        </div>
      </form>
    </Card>
  )
}
