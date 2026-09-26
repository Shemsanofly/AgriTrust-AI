import { ArrowLeft, CheckCircle2, EyeOff, FileCheck2, Link2, Lock, ShieldAlert, ShieldCheck, ShoppingBasket, Sprout, Warehouse, type LucideIcon } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { CropImage } from '../../components/crops'
import { BrandMark } from '../../components/Layout'
import { LanguageSwitcher } from '../../components/LanguageSwitcher'
import { Card, ErrorState, KeyValues, Loading, Notice, RiskBadge, SimulatedTag, StatusBadge, VerifyBadge, cx } from '../../components/ui'
import { useAuth } from '../../lib/auth'
import { useApi, useBi, useErrorText, useFormat } from '../../lib/hooks'
import { QrImage } from '../ghala/BatchParts'
import { QrScanner } from './QrScanner'

type Check = { entity_type: string; entity_id: string; status: string; tx_hash?: string; block_number?: number; anchored_at?: number; mode?: string; issuer?: string }
type Stage = { stage: 'SHAMBANI' | 'GHALANI' | 'SOKONI'; facts: Record<string, any>; checks: Check[] }
type Result = { record_id: string; batch_id: string; status: string; chain_mode: string; stages: Stage[]; note: { en: string; sw: string } }


function PublicShell({ children }: { children: React.ReactNode }) {
  const { t } = useTranslation()
  const { user } = useAuth()
  return (
    <div className="min-h-dvh">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex h-14 max-w-4xl items-center justify-between gap-3 px-4">
          <Link to="/" className="flex items-center gap-2 font-semibold" aria-label={t('app.name')}>
            <BrandMark className="size-7" />
            <span className="hidden sm:inline">{t('app.name')}</span>
          </Link>
          <div className="flex items-center gap-2">
            <LanguageSwitcher compact />
            {!user && (
              <Link to="/login" className="text-sm font-medium text-forest-800">
                {t('auth.login')}
              </Link>
            )}
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-4xl px-4 py-6 pb-16">{children}</main>
    </div>
  )
}

/** Public: anyone scanning a bag's QR can check its journey. No login, no personal data. */
export function VerifyPage() {
  const { id } = useParams()
  const { user } = useAuth()
  const content = <VerifyResult id={id!} />
  if (user) return content
  return <PublicShell>{content}</PublicShell>
}

export function ScanPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const body = (
    <div className="mx-auto max-w-md">
      <h1 className="text-[22px] font-semibold tracking-tight">{t('verify.scanTitle')}</h1>
      <p className="mt-1 mb-5 text-sm text-muted">{t('verify.scanSubtitle')}</p>
      <QrScanner />
      <OnOffChain className="mt-8" />
    </div>
  )
  return user ? body : <PublicShell>{body}</PublicShell>
}

function VerifyResult({ id }: { id: string }) {
  const { t } = useTranslation()
  const bi = useBi()
  const f = useFormat()
  const errorText = useErrorText()
  const { user } = useAuth()
  const { data, loading, error, reload } = useApi<Result>(`/verify/${id}`)

  if (loading && !data) return <Loading rows={4} />
  if (error || !data) return <ErrorState text={errorText(error)} onRetry={reload} />

  const farm = data.stages.find((s) => s.stage === 'SHAMBANI')!
  const ghala = data.stages.find((s) => s.stage === 'GHALANI')
  const market = data.stages.find((s) => s.stage === 'SOKONI')
  const good = data.status === 'VERIFIED'
  const bad = data.status === 'MISMATCH'
  const BannerIcon = bad ? ShieldAlert : good ? ShieldCheck : FileCheck2

  const events: { icon: LucideIcon; title: string; detail: string; check?: Check; when?: string }[] = []
  events.push({
    icon: Sprout,
    title: t('verify.event.harvest'),
    detail: `${t(`crops.${farm.facts.crop_type}`)} · ${f.kg(farm.facts.quantity_kg)} · ${farm.facts.region}`,
    check: farm.checks[0],
    when: farm.facts.harvest_date,
  })
  if (ghala) {
    events.push({
      icon: Warehouse,
      title: t('verify.event.receipt', { id: ghala.facts.receipt_id }),
      detail: `${ghala.facts.warehouse} · ${f.kg(ghala.facts.quantity_kg)} · ${t('ghala.gradeX', { grade: ghala.facts.grade })}`,
      check: ghala.checks.find((c) => c.entity_type === 'RECEIPT'),
      when: ghala.facts.date_in,
    })
    ghala.facts.storage_windows.forEach((w: any, i: number) =>
      events.push({
        icon: Warehouse,
        title: t('verify.event.storage', { risk: t(`risk.${w.risk_level}`) }),
        detail: `${f.num(w.temp_avg, 1)}°C · ${f.num(w.rh_avg, 1)}% · ${t('verify.readings', { count: w.reading_count })}`,
        check: ghala.checks.filter((c) => c.entity_type === 'STORAGE')[i],
        when: w.window_end,
      }),
    )
  }
  market?.facts.verified_sales.forEach((s: any, i: number) =>
    events.push({
      icon: ShoppingBasket,
      title: t('verify.event.sale', { id: s.sale_id }),
      detail: f.kg(s.quantity_kg),
      check: market.checks[i],
      when: s.completed_at,
    }),
  )

  events.sort((a, b) => (a.when ?? '').localeCompare(b.when ?? ''))

  return (
    <div className="space-y-5">
      {user && (
        <button onClick={() => history.back()} className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink">
          <ArrowLeft className="size-4" aria-hidden /> {t('common.back')}
        </button>
      )}

      <section className={cx('rounded-(--radius-card) border p-5', bad ? 'border-danger-700/30 bg-danger-100' : good ? 'border-forest-200 bg-forest-50' : 'border-line bg-surface')}>
        <div className="flex flex-wrap items-start gap-4">
          <BannerIcon className={cx('size-8 shrink-0', bad ? 'text-danger-700' : good ? 'text-forest-700' : 'text-muted')} aria-hidden />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-xl font-semibold">{t(`verify.headline.${data.status}`)}</h1>
              <VerifyBadge status={data.status} />
            </div>
            <p className="mt-1 text-sm text-ink-soft">{t(`verify.meaning.${data.status}`)}</p>
            <p className="num mt-2 font-mono text-xs text-muted">{data.record_id}</p>
          </div>
          <QrImage id={data.batch_id} />
        </div>
      </section>

      <div className="grid gap-5 lg:grid-cols-[1.3fr_1fr]">
        <div className="space-y-5">
          <Card>
            <div className="flex gap-4">
              <CropImage crop={farm.facts.crop_type} className="size-16 shrink-0" />
              <div className="min-w-0 flex-1">
                <div className="text-lg font-semibold">{t(`crops.${farm.facts.crop_type}`)}</div>
                <p className="num font-mono text-xs text-muted">{data.batch_id}</p>
              </div>
            </div>
            <div className="mt-4">
              <KeyValues
                items={[
                  [t('verify.origin'), farm.facts.region],
                  [t('ghala.harvestDate'), f.date(farm.facts.harvest_date)],
                  [t('verify.currentWarehouse'), ghala ? `${ghala.facts.warehouse} · ${ghala.facts.warehouse_region}` : t('verify.notInGhala')],
                  [t('ghala.quantity'), f.kg(ghala?.facts.quantity_kg ?? farm.facts.quantity_kg)],
                  [t('verify.storageStatus'), ghala?.facts.storage_windows.length ? <RiskBadge level={ghala.facts.storage_windows.at(-1).risk_level} /> : '—'],
                  [t('verify.farmerId'), <span className="num font-mono">{farm.facts.farmer}</span>],
                ]}
              />
            </div>
          </Card>

          <Card title={t('verify.eventsTitle')} subtitle={t('verify.eventsSub')}>
            <ol className="relative space-y-5 border-l border-line pl-6">
              {events.map((e, i) => (
                <li key={i} className="relative">
                  <span className="absolute top-0 -left-[33px] flex size-5 items-center justify-center rounded-full border border-line bg-surface">
                    <e.icon className="size-3 text-muted" aria-hidden />
                  </span>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium">{e.title}</span>
                    {e.check && <VerifyBadge status={e.check.status} />}
                  </div>
                  <p className="text-[13px] text-muted">
                    {e.when && <>{f.date(e.when)} · </>}
                    {e.detail}
                  </p>
                  {e.check?.tx_hash && (
                    <p className="num mt-0.5 flex items-center gap-1 font-mono text-[11px] text-muted">
                      <Link2 className="size-3" aria-hidden /> {e.check.tx_hash.slice(0, 18)}… · #{e.check.block_number}
                    </p>
                  )}
                </li>
              ))}
            </ol>
            {data.chain_mode === 'SIMULATED' && (
              <p className="mt-4 flex flex-wrap items-center gap-2 text-xs text-muted">
                <SimulatedTag label={t('verify.localLedger')} /> {t('verify.simulatedHint')}
              </p>
            )}
          </Card>
        </div>

        <div className="space-y-5">
          {ghala && (
            <Card title={t('verify.receiptTitle')}>
              <KeyValues
                cols={1}
                items={[
                  [t('ghala.receiptNo'), <span className="num font-mono">{ghala.facts.receipt_id}</span>],
                  [t('ghala.warehouse'), ghala.facts.warehouse],
                  [t('ghala.dateIn'), f.date(ghala.facts.date_in)],
                  [t('ghala.receiptStatus'), <StatusBadge status={ghala.facts.receipt_status} />],
                ]}
              />
              <p className="mt-3 text-xs text-muted">{t('ghala.receiptLegal')}</p>
            </Card>
          )}
          <Card title={t('verify.ownershipTitle')}>
            {market?.facts.verified_sales.length ? (
              <ul className="-my-2 divide-y divide-line text-sm">
                {market.facts.verified_sales.map((s: any) => (
                  <li key={s.sale_id} className="flex items-center justify-between gap-2 py-2">
                    <span className="num font-mono text-xs">{s.sale_id}</span>
                    <span className="num">{f.kg(s.quantity_kg)}</span>
                    <span className="text-xs text-muted">{f.date(s.completed_at)}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted">{t('verify.noSales')}</p>
            )}
            <p className="mt-3 text-xs text-muted">{t('verify.ownershipNote')}</p>
          </Card>
          <OnOffChain />
          <Notice tone="neutral">{bi(data.note)}</Notice>
        </div>
      </div>
    </div>
  )
}

/** What is and is not on the blockchain, stated plainly. */
export function OnOffChain({ className = '' }: { className?: string }) {
  const { t } = useTranslation()
  const on = ['batchId', 'recordHashes', 'receipts', 'saleProofs'] as const
  const off = ['identity', 'biometrics', 'finance', 'rawIot', 'documents'] as const
  return (
    <Card title={t('verify.privacyTitle')} className={className}>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-1">
        <div>
          <div className="flex items-center gap-1.5 text-[13px] font-semibold text-forest-800">
            <Link2 className="size-4" aria-hidden /> {t('verify.onChain')}
          </div>
          <ul className="mt-1.5 space-y-1 text-[13px] text-ink-soft">
            {on.map((k) => (
              <li key={k} className="flex gap-2">
                <CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-forest-700" aria-hidden /> {t(`verify.on.${k}`)}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <div className="flex items-center gap-1.5 text-[13px] font-semibold text-ink-soft">
            <Lock className="size-4" aria-hidden /> {t('verify.offChain')}
          </div>
          <ul className="mt-1.5 space-y-1 text-[13px] text-ink-soft">
            {off.map((k) => (
              <li key={k} className="flex gap-2">
                <EyeOff className="mt-0.5 size-3.5 shrink-0 text-muted" aria-hidden /> {t(`verify.off.${k}`)}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </Card>
  )
}
