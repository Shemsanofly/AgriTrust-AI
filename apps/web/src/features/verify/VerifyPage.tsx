import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { LanguageSwitcher } from '../../components/LanguageSwitcher'
import { Card, ErrorNote, Loading, SimulatedTag, VerifyBadge } from '../../components/ui'
import { apiUrl } from '../../lib/api'
import { useApi, useBi, useErrorText, useFormat } from '../../lib/hooks'

const STAGE_ICON: Record<string, string> = { SHAMBANI: '🌱', GHALANI: '🏚️', SOKONI: '🧺' }

/** Public page opened by scanning a QR on a bag or receipt. No login needed. */
export function VerifyPage() {
  const { id } = useParams()
  const { t } = useTranslation()
  const bi = useBi()
  const f = useFormat()
  const errorText = useErrorText()
  const { data, loading, error } = useApi<any>(`/verify/${id}`)

  return (
    <div className="min-h-screen bg-paper">
      <header className="bg-brand-900 text-white">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3">
          <Link to="/" className="font-bold">
            🌱 {t('app.name')}
          </Link>
          <LanguageSwitcher tone="dark" />
        </div>
      </header>
      <main className="mx-auto max-w-3xl space-y-4 px-4 py-6">
        <h1 className="text-xl font-bold">🔎 {t('verify.title')}</h1>
        {loading && !data && <Loading />}
        {error && <ErrorNote text={errorText(error)} />}
        {data && (
          <>
            <Card>
              <div className="flex flex-wrap items-center gap-4">
                <img src={apiUrl(`/qr/${data.record_id}.svg`)} alt="QR" className="h-24 w-24 rounded-lg border" />
                <div className="flex-1">
                  <div className="font-mono text-lg font-semibold">{data.record_id}</div>
                  <div className="mt-2 text-lg">
                    <VerifyBadge status={data.status} />
                  </div>
                  <p className="mt-2 text-sm text-stone-600">{t(`verify.meaning.${data.status}`)}</p>
                  {data.chain_mode === 'SIMULATED' && (
                    <p className="mt-1 text-xs text-stone-500">
                      <SimulatedTag label={t('verify.simulatedLedger')} /> {t('verify.simulatedHint')}
                    </p>
                  )}
                </div>
              </div>
            </Card>

            <ol className="space-y-3">
              {data.stages.map((stage: any) => (
                <li key={stage.stage}>
                  <Card title={`${STAGE_ICON[stage.stage]} ${t(`verify.stages.${stage.stage}`)}`}>
                    <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-3">
                      {Object.entries(stage.facts)
                        .filter(([k]) => !['storage_windows', 'verified_sales'].includes(k))
                        .map(([k, v]) => (
                          <div key={k}>
                            <dt className="text-xs text-stone-500">{t(`verify.facts.${k}`, { defaultValue: k })}</dt>
                            <dd className="font-medium">{k === 'crop_type' ? t(`crops.${v}`) : k.endsWith('date') || k === 'date_in' ? f.date(String(v)) : String(v)}</dd>
                          </div>
                        ))}
                    </dl>
                    {stage.facts.storage_windows?.length > 0 && (
                      <div className="mt-3 text-sm">
                        <div className="text-xs text-stone-500">{t('verify.storageWindows')}</div>
                        <ul className="mt-1 space-y-1">
                          {stage.facts.storage_windows.map((w: any, i: number) => (
                            <li key={i}>
                              {f.dateTime(w.window_start)} → {f.dateTime(w.window_end)} · {f.num(w.temp_avg, 1)}°C · {f.num(w.rh_avg, 1)}% · {t(`risk.${w.risk_level}`)} ({w.reading_count})
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {stage.facts.verified_sales?.map((s: any) => (
                      <p key={s.sale_id} className="text-sm">
                        {s.sale_id} · {f.num(s.quantity_kg)} kg · {f.date(s.completed_at)}
                      </p>
                    ))}
                    <ul className="mt-3 space-y-1 border-t border-stone-100 pt-2 text-xs">
                      {stage.checks.map((c: any, i: number) => (
                        <li key={i} className="flex flex-wrap items-center gap-2">
                          <VerifyBadge status={c.status} />
                          <span className="font-mono">
                            {t(`verify.types.${c.entity_type}`)} {c.entity_id}
                          </span>
                          {c.tx_hash && (
                            <span className="truncate font-mono text-stone-500" title={c.tx_hash}>
                              tx {c.tx_hash.slice(0, 14)}… · #{c.block_number}
                            </span>
                          )}
                        </li>
                      ))}
                    </ul>
                  </Card>
                </li>
              ))}
            </ol>
            <p className="rounded-xl bg-stone-100 p-3 text-sm text-stone-700">ℹ️ {bi(data.note)}</p>
          </>
        )}
      </main>
    </div>
  )
}
