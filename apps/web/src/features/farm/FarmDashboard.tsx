import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { AlertsPanel } from '../../components/AlertsPanel'
import { TimeSeriesChart, pivotReadings } from '../../components/Charts'
import { Badge, Button, Card, Empty, ErrorNote, Field, Loading, SimulatedTag, Stat, Tabs } from '../../components/ui'
import { api } from '../../lib/api'
import { useApi, useBi, useErrorText, useFormat, type Bi } from '../../lib/hooks'

type Farm = {
  id: number
  name: string
  region: string
  acreage: number
  soil_type: string
  irrigation_type: string
  crops: { id: number; crop_type: string; variety?: string; growth_stage: string; planting_date: string; expected_harvest_date?: string }[]
  sensors: { device_id: string; type: string; simulated: boolean; last_seen_at: string | null }[]
  latest: Record<string, { value: number; ts: string; quality_flag: string }>
}

type Advice = {
  id: number
  action: 'IRRIGATE' | 'SKIP_RAIN' | 'NO_ACTION' | 'CHECK_SENSOR'
  amount_mm: number
  headline: Bi
  when: Bi
  reasons: Bi[]
  followed: boolean | null
  model_version: string
  created_at: string
  inputs: Record<string, any>
}

const STAGES = ['initial', 'vegetative', 'flowering', 'maturity'] as const

export function FarmDashboard() {
  const { t } = useTranslation()
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
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-bold">🌱 {t('farm.title')}</h1>
        <Button variant="secondary" onClick={() => setShowAdd((v) => !v)}>
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
      {farms && farms.length > 1 && <Tabs tabs={farms.map((f) => ({ id: String(f.id), label: f.name }))} value={String(farmId)} onChange={(id) => setFarmId(Number(id))} />}
      {!farms?.length && <Empty>{t('farm.noFarms')}</Empty>}
      {farm && <FarmView key={`${farm.id}-${tick}`} farm={farm} onChanged={() => (reloadFarms(), setTick((x) => x + 1))} />}
      <AlertsPanel refreshKey={tick} />
    </div>
  )
}

function FarmView({ farm, onChanged }: { farm: Farm; onChanged: () => void }) {
  const { t } = useTranslation()
  const bi = useBi()
  const f = useFormat()
  const errorText = useErrorText()
  const crop = farm.crops.find((c) => c.growth_stage !== 'harvested')
  const soilSensor = farm.sensors.find((s) => s.type === 'soil')
  const { data: advice, error: adviceError, reload: reloadAdvice } = useApi<Advice>(crop && soilSensor ? `/farms/${farm.id}/irrigation-advice` : null)
  const { data: readings } = useApi<{ ts: string; metric: string; value: number }[]>(`/farms/${farm.id}/readings?hours=48`)
  const { data: weather } = useApi<{ simulated: boolean; source: string; days: { date: string; rain_mm: number; et0_mm: number; tmax_c: number }[] }>(`/farms/${farm.id}/weather`)
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
  const tone = advice?.action === 'IRRIGATE' ? 'border-sky-300 bg-sky-50' : advice?.action === 'CHECK_SENSOR' ? 'border-amber-300 bg-amber-50' : 'border-green-300 bg-green-50'

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat label={t('farm.soilMoisture')} value={moisture ? `${f.num(moisture.value, 1)}%` : '—'} sub={moisture && f.dateTime(moisture.ts)} />
        <Stat label={t('farm.soilTemp')} value={soilTemp ? `${f.num(soilTemp.value, 1)}°C` : '—'} />
        <Stat label={t('farm.crop')} value={crop ? t(`crops.${crop.crop_type}`, { defaultValue: crop.crop_type }) : '—'} sub={crop && t(`stages.${crop.growth_stage}`)} />
        <Stat label={t('farm.acreage')} value={`${f.num(farm.acreage, 1)} ${t('farm.acres')}`} sub={`${t(`soil.${farm.soil_type}`, { defaultValue: farm.soil_type })} · ${t(`irrigation.${farm.irrigation_type}`, { defaultValue: farm.irrigation_type })}`} />
      </div>

      {crop && soilSensor && (
        <section className={`rounded-2xl border-2 p-4 ${tone}`} aria-live="polite">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-semibold tracking-wide text-stone-600 uppercase">💧 {t('farm.advice')}</h2>
            <div className="flex gap-1">
              <Badge tone="blue">{t('farm.rulesModel')}</Badge>
              {weather?.simulated && <SimulatedTag label={t('farm.weatherSimulated')} />}
            </div>
          </div>
          {adviceError ? (
            <ErrorNote text={errorText(adviceError)} />
          ) : advice ? (
            <>
              <p className="mt-2 text-2xl font-bold text-stone-900">{bi(advice.headline)}</p>
              <p className="mt-3 text-sm font-medium text-stone-700">{t('farm.why')}</p>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-stone-700">
                {advice.reasons.map((r, i) => (
                  <li key={i}>{bi(r)}</li>
                ))}
              </ul>
              {(advice.action === 'IRRIGATE' || advice.action === 'SKIP_RAIN') && (
                <div className="mt-4 flex flex-wrap items-center gap-2">
                  {advice.followed == null ? (
                    <>
                      <span className="text-sm text-stone-600">{t('farm.didYouFollow')}</span>
                      <Button busy={busy === 'yes'} onClick={() => run('yes', () => api(`/advice/${advice.id}/feedback`, { method: 'POST', body: { followed: true } }).then(reloadAdvice))}>
                        👍 {t('common.yes')}
                      </Button>
                      <Button variant="secondary" busy={busy === 'no'} onClick={() => run('no', () => api(`/advice/${advice.id}/feedback`, { method: 'POST', body: { followed: false } }).then(reloadAdvice))}>
                        {t('common.no')}
                      </Button>
                    </>
                  ) : (
                    <Badge tone={advice.followed ? 'green' : 'stone'}>{advice.followed ? t('farm.followed') : t('farm.notFollowed')}</Badge>
                  )}
                </div>
              )}
              <p className="mt-3 text-xs text-stone-500">
                {advice.model_version} · {f.dateTime(advice.created_at)}
              </p>
            </>
          ) : (
            <Loading />
          )}
        </section>
      )}

      <Card
        title={t('farm.readings48h')}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {soilSensor?.simulated && <SimulatedTag />}
            <Button variant="secondary" className="min-h-8 px-3 text-xs" busy={busy === 'dry'} onClick={() => run('dry', () => api('/demo/scenario/soil-drying', { method: 'POST' }))}>
              ☀️ {t('farm.demoDry')}
            </Button>
            <Button variant="secondary" className="min-h-8 px-3 text-xs" busy={busy === 'wet'} onClick={() => run('wet', () => api('/demo/scenario/soil-wet', { method: 'POST' }))}>
              🌧️ {t('farm.demoWet')}
            </Button>
          </div>
        }
      >
        <ErrorNote text={error} />
        {readings?.length ? (
          <TimeSeriesChart
            data={pivotReadings(readings)}
            series={[
              { key: 'soil_moisture_pct', label: t('farm.soilMoisture'), unit: '%', color: '#0284c7', limit: crop ? advice?.inputs?.refill_threshold_pct : undefined },
              { key: 'soil_temperature_c', label: t('farm.soilTemp'), unit: '°C', color: '#c2410c' },
            ]}
          />
        ) : (
          <Empty>{soilSensor ? t('farm.noReadings') : t('farm.noSensor')}</Empty>
        )}
      </Card>

      {weather && (
        <Card title={t('farm.weather')} actions={weather.simulated ? <SimulatedTag /> : <Badge tone="blue">Open-Meteo</Badge>}>
          <div className="grid grid-cols-4 gap-2 sm:grid-cols-7">
            {weather.days.map((d) => (
              <div key={d.date} className="rounded-xl bg-stone-50 p-2 text-center text-xs">
                <div className="font-medium text-stone-600">{f.weekday(d.date)}</div>
                <div className="my-1 text-lg">{d.rain_mm >= 2 ? '🌧️' : d.tmax_c >= 30 ? '☀️' : '⛅'}</div>
                <div className="font-semibold">{f.num(d.rain_mm, 1)} mm</div>
                <div className="text-stone-500">{f.num(d.tmax_c)}°C</div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {crop && (
        <Card title={t('farm.cropStage')}>
          <div className="flex flex-wrap gap-2">
            {STAGES.map((stage) => (
              <Button
                key={stage}
                variant={crop.growth_stage === stage ? 'primary' : 'secondary'}
                className="min-h-8 px-3 text-xs"
                onClick={() => run(`stage-${stage}`, () => api(`/crops/${crop.id}`, { method: 'PATCH', body: { growth_stage: stage } }))}
              >
                {t(`stages.${stage}`)}
              </Button>
            ))}
          </div>
          <p className="mt-2 text-xs text-stone-500">
            {t('farm.planted')}: {f.date(crop.planting_date)} · {t('farm.expectedHarvest')}: {f.date(crop.expected_harvest_date)}
          </p>
        </Card>
      )}
    </div>
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
