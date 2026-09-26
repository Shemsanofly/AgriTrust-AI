import { CloudRain, Droplets, FlaskConical, Radio, Sun, ThumbsDown, ThumbsUp } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Badge, Button, ErrorNote, Recommendation, Skeleton, useToast } from '../../components/ui'
import { api } from '../../lib/api'
import { useApi, useBi, useErrorText, useFormat } from '../../lib/hooks'
import type { Advice } from './shared'

const TONE = { IRRIGATE: 'blue', SKIP_RAIN: 'green', NO_ACTION: 'green', CHECK_SENSOR: 'amber' } as const
const ICON = { IRRIGATE: Droplets, SKIP_RAIN: CloudRain, NO_ACTION: Droplets, CHECK_SENSOR: Radio }

/** Today's irrigation recommendation for one farm, with the reasons and the farmer's
 * feedback (whether they followed it feeds their verified farm activity). */
export function IrrigationCard({ farmId, refreshKey = 0, onChanged, showDemo = true }: { farmId: number; refreshKey?: number; onChanged?: () => void; showDemo?: boolean }) {
  const { t } = useTranslation()
  const bi = useBi()
  const f = useFormat()
  const toast = useToast()
  const errorText = useErrorText()
  const { data: advice, error, reload } = useApi<Advice>(`/farms/${farmId}/irrigation-advice`, [refreshKey])
  const [busy, setBusy] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)

  const run = async (key: string, fn: () => Promise<unknown>, done?: string) => {
    setBusy(key)
    setErr(null)
    try {
      await fn()
      reload()
      onChanged?.()
      if (done) toast(done)
    } catch (e) {
      setErr(errorText(e))
    } finally {
      setBusy(null)
    }
  }

  if (error) return <ErrorNote text={errorText(error)} />
  if (!advice) return <Skeleton className="h-44" />

  const actionable = advice.action === 'IRRIGATE' || advice.action === 'SKIP_RAIN'
  return (
    <div className="space-y-2">
      <Recommendation
        tone={TONE[advice.action]}
        icon={ICON[advice.action]}
        label={t(`irrigation.label.${advice.action}`)}
        headline={bi(advice.headline)}
        reasons={advice.reasons.map((r) => bi(r))}
        meta={`${t('irrigation.basedOn')} · ${f.relative(advice.created_at)} · ${advice.model_version}`}
      >
        {actionable &&
          (advice.followed == null ? (
            <div className="flex flex-wrap items-center gap-2">
              <span className="mr-1 text-[13px] text-ink-soft">{advice.action === 'IRRIGATE' ? t('irrigation.askIrrigated') : t('irrigation.askWaited')}</span>
              <Button size="sm" icon={ThumbsUp} busy={busy === 'yes'} onClick={() => run('yes', () => api(`/advice/${advice.id}/feedback`, { method: 'POST', body: { followed: true } }), t('irrigation.thanks'))}>
                {t('common.yes')}
              </Button>
              <Button size="sm" variant="secondary" icon={ThumbsDown} busy={busy === 'no'} onClick={() => run('no', () => api(`/advice/${advice.id}/feedback`, { method: 'POST', body: { followed: false } }))}>
                {t('common.no')}
              </Button>
            </div>
          ) : (
            <Badge tone={advice.followed ? 'green' : 'stone'}>{advice.followed ? t('irrigation.followed') : t('irrigation.notFollowed')}</Badge>
          ))}
      </Recommendation>
      <ErrorNote text={err} />
      {showDemo && (
        <details className="group text-[13px]">
          <summary className="inline-flex cursor-pointer items-center gap-1.5 rounded px-1 py-1 text-muted hover:text-ink">
            <FlaskConical className="size-3.5" aria-hidden /> {t('demo.controls')}
          </summary>
          <div className="mt-2 flex flex-wrap gap-2">
            <Button size="sm" variant="secondary" icon={Sun} busy={busy === 'dry'} onClick={() => run('dry', async () => { await api('/demo/weather/dry', { method: 'POST' }); await api('/demo/scenario/soil-drying', { method: 'POST' }) })}>
              {t('demo.soilDrying')}
            </Button>
            <Button size="sm" variant="secondary" icon={CloudRain} busy={busy === 'rain'} onClick={() => run('rain', async () => { await api('/demo/scenario/soil-drying', { method: 'POST' }); await api('/demo/weather/rain', { method: 'POST' }) })}>
              {t('demo.rainComing')}
            </Button>
            <Button size="sm" variant="secondary" icon={Droplets} busy={busy === 'wet'} onClick={() => run('wet', async () => { await api('/demo/weather/live', { method: 'POST' }); await api('/demo/scenario/soil-wet', { method: 'POST' }) })}>
              {t('demo.afterRain')}
            </Button>
          </div>
        </details>
      )}
    </div>
  )
}
