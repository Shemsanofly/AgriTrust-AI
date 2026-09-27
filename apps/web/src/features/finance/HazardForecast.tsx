import { CloudRain, Flame, Lightbulb, RefreshCw, Sun, Waves, type LucideIcon } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Badge, Button, Card, ErrorState, Skeleton, Tabs, cx, type Tone } from '../../components/ui'
import { useApi, useBi, useErrorText, useFormat, type Bi } from '../../lib/hooks'

type Hazard = {
  hazard: 'drought' | 'fire' | 'flood'
  probability: number
  level: 'low' | 'moderate' | 'high' | 'severe'
  window_days: number
  start: string
  end: string
  peak_day?: string | null
  drivers: Bi[]
  recommendations: Bi[]
  insurance: string
}
type FarmForecast = { farm_id: number; name: string; region: string; hazards: Hazard[]; available: { weather: boolean; river: boolean; normals: boolean } }
type Forecast = { generated_at: string; farms: FarmForecast[]; sources: string[] }

const ICON: Record<Hazard['hazard'], LucideIcon> = { drought: Sun, fire: Flame, flood: Waves }
const TONE: Record<Hazard['level'], Tone> = { low: 'green', moderate: 'gold', high: 'amber', severe: 'red' }
const BAR: Record<Hazard['level'], string> = { low: 'bg-forest-700', moderate: 'bg-harvest-500', high: 'bg-warn-700', severe: 'bg-danger-700' }

/** AI forecast of drought, fire and flood for the farmer's farms, with what to do about each. */
export function HazardForecast({ onInsurance }: { onInsurance?: (product: string) => void }) {
  const { t } = useTranslation()
  const bi = useBi()
  const f = useFormat()
  const errorText = useErrorText()
  const { data, loading, error, reload } = useApi<Forecast>('/insurance/hazards')
  const [farmId, setFarmId] = useState<string | null>(null)

  if (loading && !data)
    return (
      <Card title={t('hazard.title')} subtitle={t('hazard.loading')}>
        <Skeleton className="h-40" />
      </Card>
    )
  if (error || !data) return <ErrorState text={errorText(error)} onRetry={reload} />
  if (!data.farms.length) return null
  const farm = data.farms.find((x) => String(x.farm_id) === farmId) ?? data.farms[0]
  const worst = [...farm.hazards].sort((a, b) => b.probability - a.probability)[0]

  return (
    <Card
      title={t('hazard.title')}
      subtitle={t('hazard.subtitle')}
      actions={
        <Button size="sm" variant="ghost" icon={RefreshCw} onClick={reload}>
          {t('hazard.refresh')}
        </Button>
      }
    >
      {data.farms.length > 1 && (
        <div className="mb-4">
          <Tabs value={String(farm.farm_id)} onChange={setFarmId} tabs={data.farms.map((x) => ({ id: String(x.farm_id), label: x.name }))} />
        </div>
      )}
      {!farm.hazards.length ? (
        <p className="text-sm text-muted">{t('hazard.unavailable')}</p>
      ) : (
        <>
          {worst && worst.level !== 'low' && (
            <p className={cx('mb-4 rounded-md px-3 py-2 text-sm font-medium', worst.level === 'severe' ? 'bg-danger-100 text-danger-700' : worst.level === 'high' ? 'bg-warn-100 text-warn-700' : 'bg-harvest-100 text-harvest-800')}>
              {t('hazard.headline', { hazard: t(`hazard.names.${worst.hazard}`), level: t(`hazard.levels.${worst.level}`), farm: farm.name })}
            </p>
          )}
          <div className="grid gap-4 lg:grid-cols-3">
            {farm.hazards.map((h) => {
              const Icon = ICON[h.hazard]
              const pct = Math.round(h.probability * 100)
              return (
                <section key={h.hazard} className="rounded-md border border-line p-3.5" aria-label={t(`hazard.names.${h.hazard}`)}>
                  <div className="flex items-center justify-between gap-2">
                    <span className="flex items-center gap-2 font-semibold">
                      <Icon className="size-5 text-ink-soft" aria-hidden /> {t(`hazard.names.${h.hazard}`)}
                    </span>
                    <Badge tone={TONE[h.level]}>{t(`hazard.levels.${h.level}`)}</Badge>
                  </div>
                  <div className="mt-2 flex items-center gap-2">
                    <div className="h-2 flex-1 overflow-hidden rounded-full bg-line" role="img" aria-label={t('hazard.chance', { pct })}>
                      <div className={cx('h-full rounded-full', BAR[h.level])} style={{ width: `${Math.max(pct, 3)}%` }} />
                    </div>
                    <span className="num w-10 text-right text-sm font-semibold">{pct}%</span>
                  </div>
                  <p className="mt-1 text-xs text-muted">
                    {t('hazard.window', { start: f.date(h.start), end: f.date(h.end) })}
                    {h.peak_day && h.level !== 'low' ? ` · ${t('hazard.peak', { day: f.date(h.peak_day) })}` : ''}
                  </p>
                  <ul className="mt-3 space-y-1 text-[13px] text-ink-soft">
                    {h.drivers.map((d, i) => (
                      <li key={i} className="flex gap-1.5">
                        <CloudRain className="mt-0.5 size-3.5 shrink-0 text-muted" aria-hidden />
                        <span>{bi(d)}</span>
                      </li>
                    ))}
                  </ul>
                  <h4 className="mt-3 text-[13px] font-semibold">{t('hazard.whatToDo')}</h4>
                  <ul className="mt-1 space-y-1.5 text-[13px]">
                    {h.recommendations.map((r, i) => (
                      <li key={i} className="flex gap-1.5 text-harvest-800">
                        <Lightbulb className="mt-0.5 size-3.5 shrink-0" aria-hidden />
                        <span className="text-ink">{bi(r)}</span>
                      </li>
                    ))}
                  </ul>
                  {h.level !== 'low' && onInsurance && (
                    <Button size="sm" variant="secondary" className="mt-3" onClick={() => onInsurance(h.insurance)}>
                      {t('hazard.coverCta', { product: t(`products.${h.insurance}`) })}
                    </Button>
                  )}
                </section>
              )
            })}
          </div>
        </>
      )}
      <p className="mt-4 text-[11px] text-muted">
        {t('hazard.method')} {t('hazard.sources', { sources: data.sources.join('; ') })} {t('hazard.updated', { time: f.relative(data.generated_at) })}
      </p>
    </Card>
  )
}
