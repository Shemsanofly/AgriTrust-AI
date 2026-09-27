import { Check, CloudRain, LocateFixed, Plus, Radio, Sparkles, Sun, CloudSun } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { ChartLegend, CHART, TimeSeriesChart, pivotReadings } from '../../components/Charts'
import { cropIcon } from '../../components/crops'
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
  Segmented,
  SimulatedTag,
  Skeleton,
  cx,
  useToast,
  type Tone,
} from '../../components/ui'
import { api } from '../../lib/api'
import { useApi, useBi, useErrorText, useFormat, type Bi } from '../../lib/hooks'
import { MOISTURE_IDEAL, STAGES, seasonProgress, type Farm, type Weather } from './shared'

type PlantingAdvice = {
  headline: Bi
  soil_summary: Bi
  tips: Bi[]
  recommendations: { crop_type: string; fit: 'excellent' | 'good' | 'fair' | 'poor'; fit_label: Bi; name: Bi; reason: Bi }[]
  current_crop: { crop_type: string; fit: string; fit_label: Bi; name: Bi; note: Bi } | null
  soil_profile?: {
    ph: number | null
    ph_band: string | null
    ph_note: Bi | null
    nutrients: Record<'N' | 'P' | 'K', string | null>
    nutrient_notes: Bi[]
    organic_matter_pct: number | null
    source: string | null
  }
  model_version: string
}

type FarmSetupPrediction = {
  soil_type: string
  crop_type: string
  irrigation_type: string
  soil_moisture_pct: number
  soil_temperature_c: number
  soil_ph: number
  soil_nitrogen: 'low' | 'medium' | 'high'
  soil_phosphorus: 'low' | 'medium' | 'high'
  soil_potassium: 'low' | 'medium' | 'high'
  confidence: 'low' | 'medium' | 'high'
  reasons: Bi[]
  source: string
  model_version: string
}

const FIT_TONE: Record<string, Tone> = { excellent: 'green', good: 'green', fair: 'amber', poor: 'red' }

export function MyFarmPage() {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const { data: farms, loading, error, reload } = useApi<Farm[]>('/farms')
  const [farmId, setFarmId] = useState<number | null>(null)
  const [adding, setAdding] = useState(false)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    if (farms?.length && !farms.some((f) => f.id === farmId)) setFarmId(farms[0].id)
  }, [farms, farmId])

  const farm = farms?.find((f) => f.id === farmId)
  return (
    <div>
      <PageHeader
        title={t('farm.title')}
        subtitle={t('farm.subtitle')}
        actions={
          <Button variant="secondary" icon={Plus} onClick={() => setAdding(true)}>
            {t('farm.addFarm')}
          </Button>
        }
      />
      {loading && !farms ? (
        <Loading rows={4} />
      ) : error ? (
        <ErrorState text={errorText(error)} onRetry={reload} />
      ) : !farms?.length ? (
        <Card>
          <EmptyState title={t('farm.noFarms')} body={t('farm.noFarmsBody')} action={<Button icon={Plus} onClick={() => setAdding(true)}>{t('farm.addFarm')}</Button>} />
        </Card>
      ) : (
        <>
          {farms.length > 1 && (
            <div className="mb-4 overflow-x-auto">
              <Segmented label={t('farm.chooseFarm')} value={String(farmId)} onChange={(id) => setFarmId(Number(id))} options={farms.map((f) => ({ id: String(f.id), label: f.name }))} />
            </div>
          )}
          {farm && <FarmView key={`${farm.id}-${tick}`} farm={farm} onChanged={() => (reload(), setTick((x) => x + 1))} />}
        </>
      )}
      <AddFarmDialog
        open={adding}
        onClose={() => setAdding(false)}
        onDone={() => {
          setAdding(false)
          reload()
        }}
      />
    </div>
  )
}

function FarmView({ farm, onChanged }: { farm: Farm; onChanged: () => void }) {
  const { t } = useTranslation()
  const f = useFormat()
  const soilSensor = farm.sensors.find((s) => s.type === 'soil')
  const { data: planting, error: plantingError } = useApi<PlantingAdvice>(`/farms/${farm.id}/planting-advice`)
  const { data: readings } = useApi<{ ts: string; metric: string; value: number }[]>(soilSensor ? `/farms/${farm.id}/readings?hours=48` : null)
  const { data: weather } = useApi<Weather>(`/farms/${farm.id}/weather`)
  const errorText = useErrorText()
  const pivoted = readings?.length ? pivotReadings(readings) : null
  const chartRows = pivoted ? displayReadings(pivoted, Boolean(soilSensor?.simulated)) : null

  return (
    <div className="space-y-5">
      <div className="grid gap-5 lg:grid-cols-[1.4fr_1fr]">
        <div className="space-y-5">
          <Card
            title={t('farm.readings48h')}
            subtitle={soilSensor ? `${soilSensor.device_id} · ${soilSensor.last_seen_at ? t('farm.lastSeen', { time: f.relative(soilSensor.last_seen_at) }) : t('farm.neverSeen')}` : undefined}
            actions={soilSensor?.simulated && <SimulatedTag />}
          >
            {!soilSensor ? (
              <EmptyState compact icon={Radio} title={t('farm.noSensor')} body={t('farm.noSensorBody')} />
            ) : !chartRows ? (
              <Skeleton className="h-48" />
            ) : (
              <div className="space-y-4">
                <div>
                  <div className="mb-1 flex items-baseline justify-between text-sm">
                    <span className="font-medium">{t('farm.soilMoisture')}</span>
                    <span className="text-xs text-muted">{t('farm.idealRange', { min: MOISTURE_IDEAL.min, max: MOISTURE_IDEAL.max })}</span>
                  </div>
                  <TimeSeriesChart height={170} data={chartRows} band={{ from: MOISTURE_IDEAL.min, to: MOISTURE_IDEAL.max }} series={[{ key: 'soil_moisture_pct', label: t('farm.soilMoisture'), unit: '%', color: CHART.moisture }]} />
                </div>
                <div>
                  <div className="mb-1 text-sm font-medium">{t('farm.soilTemp')}</div>
                  <TimeSeriesChart height={130} data={chartRows} series={[{ key: 'soil_temperature_c', label: t('farm.soilTemp'), unit: '°C', color: CHART.temperature }]} />
                </div>
                <ChartLegend items={[{ label: t('farm.idealBand'), color: CHART.band }, ...(soilSensor.simulated ? [{ label: t('farm.aiEstimate'), color: CHART.axis, dashed: true }] : [])]} />
              </div>
            )}
          </Card>

          <CropsCard farm={farm} onChanged={onChanged} fits={planting?.recommendations} />
        </div>

        <div className="space-y-5">
          <Card title={t('farm.details')}>
            <KeyValues
              items={[
                [t('auth.region'), farm.region],
                [t('farm.acreage'), `${f.num(farm.acreage, 1)} ${t('farm.acres')}`],
                [t('farm.soilType'), t(`soil.${farm.soil_type}`, { defaultValue: farm.soil_type })],
                [t('farm.irrigationType'), t(`irrigation.${farm.irrigation_type}`, { defaultValue: farm.irrigation_type })],
                [t('farm.location'), <span className="num">{f.num(farm.lat, 4)}, {f.num(farm.lon, 4)}</span>],
                [t('farm.registered'), f.date(farm.created_at)],
              ]}
            />
          </Card>
          <SoilCard farm={farm} planting={planting} />
          {weather && <WeatherCard weather={weather} />}
        </div>
      </div>

      <Card title={t('farm.advice')} subtitle={t('farm.adviceSub')} actions={<Badge tone="stone">{t('common.rules')}</Badge>}>
        {plantingError ? (
          <ErrorNote text={errorText(plantingError)} />
        ) : !planting ? (
          <Skeleton className="h-40" />
        ) : (
          <PlantingAdviceBody planting={planting} />
        )}
      </Card>
    </div>
  )
}

function displayReadings(rows: Record<string, any>[], estimated: boolean) {
  if (!estimated || rows.length !== 1) return rows
  const base = rows[0]
  const t = new Date(base.ts).getTime()
  if (!Number.isFinite(t)) return rows
  return [-30, 0, 30].map((minutes) => ({
    ...base,
    ts: new Date(t + minutes * 60_000).toISOString(),
  }))
}

function SoilCard({ farm, planting }: { farm: Farm; planting: PlantingAdvice | null }) {
  const { t } = useTranslation()
  const bi = useBi()
  const f = useFormat()
  const sp = planting?.soil_profile
  const levels: [string, string | null | undefined][] = [
    ['N', farm.soil_nitrogen],
    ['P', farm.soil_phosphorus],
    ['K', farm.soil_potassium],
  ]
  const hasTest = farm.soil_ph != null || levels.some(([, v]) => v)
  return (
    <Card title={t('farm.soilProfile')} subtitle={farm.soil_source ? t(`farm.soilSource.${farm.soil_source}`) : undefined}>
      {!hasTest ? (
        <EmptyState compact title={t('farm.noSoilTest')} body={t('farm.noSoilTestBody')} />
      ) : (
        <div className="space-y-4">
          {farm.soil_ph != null && (
            <div>
              <div className="flex items-baseline justify-between">
                <span className="text-sm text-muted">pH</span>
                <span className="num text-lg font-semibold">{f.num(farm.soil_ph, 1)}</span>
              </div>
              <PhScale ph={farm.soil_ph} />
              {sp?.ph_note && <p className="mt-2 text-[13px] text-ink-soft">{bi(sp.ph_note)}</p>}
            </div>
          )}
          {levels.some(([, v]) => v) && (
            <div className="grid grid-cols-3 gap-2">
              {levels.map(([k, v]) => (
                <div key={k} className="rounded-md bg-sunken px-3 py-2">
                  <div className="text-xs text-muted">{t(`nutrients.${k}`)}</div>
                  <div className={cx('text-sm font-semibold', v === 'low' && 'text-warn-700')}>{v ? t(`levels.${v}`) : '—'}</div>
                </div>
              ))}
            </div>
          )}
          {farm.organic_matter_pct != null && (
            <p className="text-[13px] text-muted">{t('farm.organicMatter', { pct: f.num(farm.organic_matter_pct, 1) })}</p>
          )}
          {sp?.nutrient_notes?.map((n, i) => (
            <p key={i} className="text-[13px] text-warn-700">
              {bi(n)}
            </p>
          ))}
        </div>
      )}
    </Card>
  )
}

/** pH 4–9 scale with the ideal band (5.8–7.0) and the farm's reading. */
function PhScale({ ph }: { ph: number }) {
  const pos = (v: number) => `${Math.min(100, Math.max(0, ((v - 4) / 5) * 100))}%`
  return (
    <div className="mt-2" aria-hidden>
      <div className="relative h-2 rounded-full bg-gradient-to-r from-[#c8553d] via-[#e2a72e] via-45% to-[#3a6f8f]">
        <div className="absolute inset-y-[-3px] rounded border-2 border-forest-800/70" style={{ left: pos(5.8), width: `calc(${pos(7)} - ${pos(5.8)})` }} />
        <div className="absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-ink shadow" style={{ left: pos(ph) }} />
      </div>
      <div className="mt-1 flex justify-between text-[10px] text-muted">
        <span>4</span>
        <span>7</span>
        <span>9</span>
      </div>
    </div>
  )
}

function WeatherCard({ weather }: { weather: Weather }) {
  const { t } = useTranslation()
  const f = useFormat()
  const maxRain = Math.max(1, ...weather.days.map((x) => x.rain_mm))
  return (
    <Card title={t('farm.weather')} actions={weather.simulated ? <SimulatedTag /> : <span className="text-xs text-muted">Open-Meteo</span>}>
      <ul className="-my-1 divide-y divide-line">
        {weather.days.map((d, i) => {
          const Icon = d.rain_mm >= 2 ? CloudRain : d.tmax_c >= 30 ? Sun : CloudSun
          return (
            <li key={d.date} className="grid grid-cols-[4.5rem_1.25rem_1fr_2.5rem] items-center gap-2 py-2 text-sm">
              <span className={cx(i === 0 ? 'font-semibold' : 'text-ink-soft')}>{i === 0 ? t('farm.today') : f.weekday(d.date)}</span>
              <Icon className="size-4 text-muted" aria-hidden />
              <span className="flex items-center gap-2">
                <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-sunken">
                  <span className="block h-full rounded-full bg-info-700/70" style={{ width: `${d.rain_mm > 0 ? Math.max(5, (d.rain_mm / maxRain) * 100) : 0}%` }} />
                </span>
                <span className="num w-14 text-right text-xs text-muted">{f.num(d.rain_mm, 1)} mm</span>
              </span>
              <span className="num text-right font-medium">{f.num(d.tmax_c)}°</span>
            </li>
          )
        })}
      </ul>
    </Card>
  )
}

function CropsCard({ farm, onChanged, fits }: { farm: Farm; onChanged: () => void; fits?: PlantingAdvice['recommendations'] }) {
  const { t } = useTranslation()
  const bi = useBi()
  const f = useFormat()
  const errorText = useErrorText()
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const setStage = async (cropId: number, stage: string) => {
    setBusy(`${cropId}-${stage}`)
    setError(null)
    try {
      await api(`/crops/${cropId}`, { method: 'PATCH', body: { growth_stage: stage } })
      onChanged()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(null)
    }
  }

  return (
    <Card title={t('farm.cropsTitle')}>
      <ErrorNote text={error} />
      {!farm.crops.length ? (
        <EmptyState compact title={t('farm.noCrops')} />
      ) : (
        <ul className="-my-3 divide-y divide-line">
          {farm.crops.map((c) => {
            const Icon = cropIcon(c.crop_type)
            const fit = fits?.find((r) => r.crop_type === c.crop_type)
            const progress = seasonProgress(c)
            const stageIdx = STAGES.indexOf(c.growth_stage as (typeof STAGES)[number])
            return (
              <li key={c.id} className="py-4">
                <div className="flex flex-wrap items-center gap-3">
                  <Icon className="size-5 text-harvest-700" aria-hidden />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2 font-medium">
                      {t(`crops.${c.crop_type}`)}
                      {c.variety && <span className="text-sm font-normal text-muted">{c.variety}</span>}
                      {fit && <Badge tone={FIT_TONE[fit.fit]}>{t('farm.soilFit', { fit: bi(fit.fit_label) })}</Badge>}
                    </div>
                    <div className="text-xs text-muted">
                      {t('farm.planted')} {f.date(c.planting_date)}
                      {c.expected_harvest_date && ` · ${t('farm.expectedHarvest')} ${f.date(c.expected_harvest_date)}`}
                    </div>
                  </div>
                  {c.growth_stage === 'harvested' ? <Badge>{t('stages.harvested')}</Badge> : progress != null && <span className="num text-xs text-muted">{t('farm.seasonProgress', { pct: progress })}</span>}
                </div>
                {c.growth_stage !== 'harvested' && (
                  <div className="mt-3 grid grid-cols-4 gap-1" role="group" aria-label={t('farm.cropStage')}>
                    {STAGES.map((stage, i) => {
                      const current = i === stageIdx
                      const done = i < stageIdx
                      return (
                        <button
                          key={stage}
                          type="button"
                          aria-pressed={current}
                          disabled={busy != null}
                          onClick={() => setStage(c.id, stage)}
                          className={cx(
                            'flex min-h-10 items-center justify-center gap-1 rounded-md border text-xs font-medium',
                            current ? 'border-forest-800 bg-forest-800 text-white' : done ? 'border-forest-200 bg-forest-50 text-forest-800' : 'border-line text-muted hover:border-line-strong',
                          )}
                        >
                          {done && <Check className="size-3" aria-hidden />}
                          {t(`stages.${stage}`)}
                        </button>
                      )
                    })}
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      )}
      <p className="mt-3 text-xs text-muted">{t('farm.stageHint')}</p>
    </Card>
  )
}

function PlantingAdviceBody({ planting }: { planting: PlantingAdvice }) {
  const { t } = useTranslation()
  const bi = useBi()
  return (
    <div className="grid gap-5 lg:grid-cols-[1.4fr_1fr]">
      <div>
        <p className="text-base font-semibold">{bi(planting.headline)}</p>
        <p className="mt-1 text-sm text-muted">{bi(planting.soil_summary)}</p>
        {planting.current_crop && (
          <p className="mt-3 text-sm">
            <Badge tone={FIT_TONE[planting.current_crop.fit]}>{bi(planting.current_crop.fit_label)}</Badge> <span className="text-ink-soft">{bi(planting.current_crop.note)}</span>
          </p>
        )}
        <h3 className="eyebrow mt-5 mb-2">{t('farm.recommendedCrops')}</h3>
        <ul className="divide-y divide-line rounded-md border border-line">
          {planting.recommendations.map((rec) => {
            const Icon = cropIcon(rec.crop_type)
            return (
              <li key={rec.crop_type} className="flex gap-3 px-3 py-2.5">
                <Icon className="mt-0.5 size-4 shrink-0 text-muted" aria-hidden />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2 text-sm font-medium">
                    {bi(rec.name)}
                    <Badge tone={FIT_TONE[rec.fit]}>{bi(rec.fit_label)}</Badge>
                  </div>
                  <p className="mt-0.5 text-xs text-muted">{bi(rec.reason)}</p>
                </div>
              </li>
            )
          })}
        </ul>
      </div>
      <div>
        <h3 className="eyebrow mb-2">{t('farm.plantingTips')}</h3>
        <ol className="space-y-3 text-sm text-ink-soft">
          {planting.tips.map((tip, i) => (
            <li key={i} className="flex gap-3">
              <span className="num flex size-5 shrink-0 items-center justify-center rounded-full bg-forest-100 text-[11px] font-semibold text-forest-800">{i + 1}</span>
              <span>{bi(tip)}</span>
            </li>
          ))}
        </ol>
        <p className="mt-4 text-[11px] text-muted">{planting.model_version}</p>
      </div>
    </div>
  )
}

function AddFarmDialog({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: () => void }) {
  const { t } = useTranslation()
  const bi = useBi()
  const toast = useToast()
  const errorText = useErrorText()
  const blank = {
    name: '',
    region: '',
    lat: '',
    lon: '',
    acreage: '',
    soil_type: 'loam',
    irrigation_type: 'rainfed',
    crop_type: 'maize',
    planting_date: new Date().toISOString().slice(0, 10),
    expected_harvest_date: '',
    soil_ph: '',
    soil_nitrogen: '',
    soil_phosphorus: '',
    soil_potassium: '',
  }
  const [form, setForm] = useState(blank)
  const [busy, setBusy] = useState(false)
  const [predicting, setPredicting] = useState(false)
  const [prediction, setPrediction] = useState<FarmSetupPrediction | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [touched, setTouched] = useState(false)
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value })
  const num = (v: string) => (v.trim() === '' ? null : Number(v.replace(',', '.')))

  const problems = {
    name: form.name.trim().length < 2 ? t('validation.required') : null,
    region: !form.region.trim() ? t('validation.required') : null,
    location: !(Number.isFinite(num(form.lat)) && Number.isFinite(num(form.lon)) && num(form.lat) !== null) ? t('validation.location') : null,
    acreage: !(num(form.acreage)! > 0) ? t('validation.acreage') : null,
    ph: form.soil_ph && !(num(form.soil_ph)! >= 3 && num(form.soil_ph)! <= 10) ? t('validation.ph') : null,
  }

  const useGps = () =>
    navigator.geolocation?.getCurrentPosition(
      (pos) => {
        const lat = pos.coords.latitude.toFixed(5)
        const lon = pos.coords.longitude.toFixed(5)
        setForm((f) => ({ ...f, lat, lon }))
        void predictSetup(lat, lon, form.region)
      },
      () => setError(t('farm.gpsFailed')),
    )

  const applyPrediction = (next: FarmSetupPrediction) => {
    setForm((f) => ({
      ...f,
      soil_type: next.soil_type,
      irrigation_type: next.irrigation_type,
      crop_type: next.crop_type,
      soil_ph: String(next.soil_ph),
      soil_nitrogen: next.soil_nitrogen,
      soil_phosphorus: next.soil_phosphorus,
      soil_potassium: next.soil_potassium,
    }))
  }

  const predictSetup = async (latValue = form.lat, lonValue = form.lon, regionValue = form.region) => {
    const lat = num(latValue)
    const lon = num(lonValue)
    if (!(Number.isFinite(lat) && Number.isFinite(lon) && lat !== null && lon !== null)) {
      setTouched(true)
      setError(t('validation.location'))
      return
    }
    setPredicting(true)
    setError(null)
    try {
      const next = await api<FarmSetupPrediction>('/farms/predict-setup', { method: 'POST', body: { lat, lon, region: regionValue.trim() || null } })
      setPrediction(next)
      applyPrediction(next)
      toast(t('farm.predictionApplied'))
    } catch (err) {
      setError(errorText(err))
    } finally {
      setPredicting(false)
    }
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setTouched(true)
    if (Object.values(problems).some(Boolean)) return
    setBusy(true)
    setError(null)
    try {
      const predictedPhUnchanged = prediction && num(form.soil_ph) === prediction.soil_ph
      const manualNitrogen = form.soil_nitrogen && (!prediction || form.soil_nitrogen !== prediction.soil_nitrogen)
      const manualPhosphorus = form.soil_phosphorus && (!prediction || form.soil_phosphorus !== prediction.soil_phosphorus)
      const manualPotassium = form.soil_potassium && (!prediction || form.soil_potassium !== prediction.soil_potassium)
      const hasManualTest = (form.soil_ph && !predictedPhUnchanged) || manualNitrogen || manualPhosphorus || manualPotassium
      await api('/farms', {
        method: 'POST',
        body: {
          name: form.name.trim(),
          region: form.region.trim(),
          lat: num(form.lat),
          lon: num(form.lon),
          acreage: num(form.acreage),
          soil_type: form.soil_type,
          irrigation_type: form.irrigation_type,
          soil_ph: num(form.soil_ph),
          soil_nitrogen: form.soil_nitrogen || null,
          soil_phosphorus: form.soil_phosphorus || null,
          soil_potassium: form.soil_potassium || null,
          soil_source: hasManualTest ? 'farmer' : prediction ? 'soil_map' : null,
          ai_estimated_environment: Boolean(prediction),
          crop: { crop_type: form.crop_type, planting_date: form.planting_date, expected_harvest_date: form.expected_harvest_date || null, growth_stage: 'initial' },
        },
      })
      setForm(blank)
      setPrediction(null)
      setTouched(false)
      toast(t('farm.added'))
      onDone()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  const show = (k: keyof typeof problems) => (touched ? problems[k] : null)
  const levelSelect = (k: 'soil_nitrogen' | 'soil_phosphorus' | 'soil_potassium', label: string) => (
    <Field label={label}>
      <select className="input" value={form[k]} onChange={set(k)}>
        <option value="">—</option>
        {['low', 'medium', 'high'].map((l) => (
          <option key={l} value={l}>
            {t(`levels.${l}`)}
          </option>
        ))}
      </select>
    </Field>
  )

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={t('farm.addFarm')}
      wide
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" form="add-farm" busy={busy}>
            {t('common.save')}
          </Button>
        </>
      }
    >
      <form id="add-farm" onSubmit={submit} className="grid gap-4 sm:grid-cols-2" noValidate>
        <Field label={t('farm.name')} error={show('name')}>
          <input className="input" value={form.name} onChange={set('name')} aria-invalid={Boolean(show('name'))} />
        </Field>
        <Field label={t('auth.region')} error={show('region')}>
          <input className="input" value={form.region} onChange={set('region')} aria-invalid={Boolean(show('region'))} />
        </Field>
        <Field label={t('farm.location')} error={show('location')}>
          <div className="flex gap-2">
            <input className="input" placeholder={t('farm.lat')} value={form.lat} onChange={set('lat')} inputMode="decimal" />
            <input className="input" placeholder={t('farm.lon')} value={form.lon} onChange={set('lon')} inputMode="decimal" />
            <Button variant="secondary" icon={LocateFixed} onClick={useGps} aria-label={t('farm.useGps')} className="shrink-0 px-3" />
          </div>
        </Field>
        <Field label={`${t('farm.acreage')} (${t('farm.acres')})`} error={show('acreage')}>
          <input className="input" value={form.acreage} onChange={set('acreage')} inputMode="decimal" aria-invalid={Boolean(show('acreage'))} />
        </Field>
        <div className="sm:col-span-2">
          <Button variant="gold" icon={Sparkles} busy={predicting} onClick={() => predictSetup()} disabled={busy}>
            {prediction ? t('farm.refreshPrediction') : t('farm.predictSetup')}
          </Button>
          <p className="mt-1 text-xs text-muted">{t('farm.predictSetupHint')}</p>
        </div>
        {prediction && (
          <div className="rounded-md border border-harvest-500/40 bg-harvest-100/40 p-3 sm:col-span-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <div className="text-sm font-semibold text-ink">{t('farm.predictionTitle')}</div>
                <div className="text-xs text-muted">
                  {t('farm.predictionConfidence')}: {t(`farm.confidence.${prediction.confidence}`)} / {prediction.model_version}
                </div>
              </div>
              <Badge tone={prediction.confidence === 'high' ? 'green' : prediction.confidence === 'medium' ? 'gold' : 'amber'} icon={Sparkles}>
                {t('farm.aiSuggested')}
              </Badge>
            </div>
            <div className="mt-3 grid gap-2 text-sm sm:grid-cols-3">
              <div>
                <span className="text-muted">{t('farm.soilType')}</span>
                <div className="font-medium">{t(`soil.${prediction.soil_type}`, { defaultValue: prediction.soil_type })}</div>
              </div>
              <div>
                <span className="text-muted">{t('farm.irrigationType')}</span>
                <div className="font-medium">{t(`irrigation.${prediction.irrigation_type}`, { defaultValue: prediction.irrigation_type })}</div>
              </div>
              <div>
                <span className="text-muted">{t('farm.crop')}</span>
                <div className="font-medium">{t(`crops.${prediction.crop_type}`, { defaultValue: prediction.crop_type })}</div>
              </div>
              <div>
                <span className="text-muted">{t('farm.soilMoisture')}</span>
                <div className="font-medium">{prediction.soil_moisture_pct}%</div>
              </div>
              <div>
                <span className="text-muted">{t('farm.soilTemp')}</span>
                <div className="font-medium">{prediction.soil_temperature_c}°C</div>
              </div>
              <div>
                <span className="text-muted">{t('farm.soilPh')}</span>
                <div className="font-medium">{prediction.soil_ph}</div>
              </div>
              <div>
                <span className="text-muted">{t('nutrients.N')}</span>
                <div className="font-medium">{t(`levels.${prediction.soil_nitrogen}`)}</div>
              </div>
              <div>
                <span className="text-muted">{t('nutrients.P')}</span>
                <div className="font-medium">{t(`levels.${prediction.soil_phosphorus}`)}</div>
              </div>
              <div>
                <span className="text-muted">{t('nutrients.K')}</span>
                <div className="font-medium">{t(`levels.${prediction.soil_potassium}`)}</div>
              </div>
            </div>
            <ul className="mt-3 space-y-1 text-xs text-ink-soft">
              {prediction.reasons.map((reason, i) => (
                <li key={i}>{bi(reason)}</li>
              ))}
            </ul>
            <p className="mt-2 text-xs text-muted">{t('farm.predictionOverride')}</p>
          </div>
        )}
        <Field label={t('farm.soilType')}>
          <select className="input" value={form.soil_type} onChange={set('soil_type')}>
            {['loam', 'sandy loam', 'clay', 'sandy'].map((s) => (
              <option key={s} value={s}>
                {t(`soil.${s}`)}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t('farm.irrigationType')}>
          <select className="input" value={form.irrigation_type} onChange={set('irrigation_type')}>
            {['rainfed', 'drip', 'furrow', 'sprinkler'].map((s) => (
              <option key={s} value={s}>
                {t(`irrigation.${s}`)}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t('farm.crop')}>
          <select className="input" value={form.crop_type} onChange={set('crop_type')}>
            {['maize', 'beans', 'rice', 'sorghum', 'sunflower'].map((c) => (
              <option key={c} value={c}>
                {t(`crops.${c}`)}
              </option>
            ))}
          </select>
        </Field>
        <div className="grid grid-cols-2 gap-2">
          <Field label={t('farm.planted')}>
            <input className="input" type="date" value={form.planting_date} onChange={set('planting_date')} />
          </Field>
          <Field label={t('farm.expectedHarvest')} optional>
            <input className="input" type="date" value={form.expected_harvest_date} onChange={set('expected_harvest_date')} />
          </Field>
        </div>
        <fieldset className="rounded-md border border-line p-3 sm:col-span-2">
          <legend className="px-1 text-sm font-medium">
            {t('farm.soilTest')} <span className="font-normal text-muted">({t('common.optional')})</span>
          </legend>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Field label="pH" error={show('ph')}>
              <input className="input" inputMode="decimal" placeholder="6.2" value={form.soil_ph} onChange={set('soil_ph')} />
            </Field>
            {levelSelect('soil_nitrogen', t('nutrients.N'))}
            {levelSelect('soil_phosphorus', t('nutrients.P'))}
            {levelSelect('soil_potassium', t('nutrients.K'))}
          </div>
        </fieldset>
        <div className="sm:col-span-2">
          <ErrorNote text={error} />
        </div>
      </form>
    </Dialog>
  )
}
