import { ChevronRight, ShieldCheck, Users, Wallet } from 'lucide-react'
import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { CropImage } from '../../components/crops'
import { Badge, Card, EmptyState, ErrorState, Loading, PageHeader, SimulatedTag, Stat, StatStrip, StatusBadge, VerifyBadge } from '../../components/ui'
import { useApi, useErrorText, useFormat } from '../../lib/hooks'
import type { Order } from '../orders/OrderList'
import { OnOffChain } from '../verify/VerifyPage'
import { QrScanner } from '../verify/QrScanner'
import type { Listing } from './Marketplace'

export function VerifiedBatchesPage() {
  const { t } = useTranslation()
  const f = useFormat()
  const { data: orders } = useApi<Order[]>('/orders')
  const { data: listings } = useApi<Listing[]>('/marketplace/listings')
  const mine = useMemo(() => {
    const seen = new Map<string, Order>()
    for (const o of orders ?? []) if (!seen.has(o.batch_id)) seen.set(o.batch_id, o)
    return [...seen.values()]
  }, [orders])
  return (
    <div>
      <PageHeader title={t('nav.verifiedBatches')} subtitle={t('verify.buyerSubtitle')} />
      <div className="grid gap-5 lg:grid-cols-[1fr_1.2fr]">
        <div className="space-y-5">
          <Card title={t('verify.scanTitle')}>
            <QrScanner />
          </Card>
          <OnOffChain />
        </div>
        <div className="space-y-5">
          <Card title={t('verify.yourBatches')} padded={false}>
            {!orders ? (
              <div className="p-4">
                <Loading rows={2} />
              </div>
            ) : !mine.length ? (
              <EmptyState compact icon={ShieldCheck} title={t('verify.noBatchesYet')} />
            ) : (
              <ul className="divide-y divide-line">
                {mine.map((o) => (
                  <li key={o.batch_id}>
                    <Link to={`/verify/${o.sale?.completed_at ? o.sale.id : o.batch_id}`} className="flex items-center gap-3 px-4 py-3 hover:bg-sunken/60 sm:px-5">
                      <CropImage crop={o.crop_type} className="size-10" />
                      <div className="min-w-0 flex-1">
                        <div className="text-sm font-medium">
                          {t(`crops.${o.crop_type}`)} · <span className="num font-mono text-xs text-muted">{o.batch_id}</span>
                        </div>
                        <div className="text-xs text-muted">
                          {o.farmer.display_name} · {f.kg(o.quantity_kg)}
                        </div>
                      </div>
                      <StatusBadge status={o.status} />
                      <ChevronRight className="size-4 text-muted" aria-hidden />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <Card title={t('verify.inMarket')} padded={false}>
            <ul className="divide-y divide-line">
              {(listings ?? []).map((l) => (
                <li key={l.batch_id}>
                  <Link to={`/verify/${l.batch_id}`} className="flex items-center gap-3 px-4 py-3 hover:bg-sunken/60 sm:px-5">
                    <CropImage crop={l.crop_type} className="size-10" />
                    <div className="min-w-0 flex-1 text-sm">
                      <span className="font-medium">{t(`crops.${l.crop_type}`)}</span> <span className="num font-mono text-xs text-muted">{l.batch_id}</span>
                      <div className="text-xs text-muted">{l.warehouse?.name}</div>
                    </div>
                    <VerifyBadge status={l.verification_status} />
                  </Link>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>
    </div>
  )
}

type Supplier = { key: string; name: string; farmerId: string; region: string; coop?: string | null; listings: Listing[]; orders: Order[] }

export function SuppliersPage() {
  const { t } = useTranslation()
  const f = useFormat()
  const errorText = useErrorText()
  const { data: listings, loading, error, reload } = useApi<Listing[]>('/marketplace/listings')
  const { data: orders } = useApi<Order[]>('/orders')
  const suppliers = useMemo(() => {
    const map = new Map<string, Supplier>()
    for (const l of listings ?? []) {
      const s = map.get(l.farmer.public_id) ?? { key: l.farmer.public_id, name: l.farmer.display_name, farmerId: l.farmer.public_id, region: l.farmer.region, coop: l.farmer.cooperative, listings: [], orders: [] }
      s.listings.push(l)
      map.set(s.key, s)
    }
    for (const o of orders ?? []) {
      const s = map.get(o.farmer.public_id) ?? { key: o.farmer.public_id, name: o.farmer.display_name, farmerId: o.farmer.public_id, region: o.farmer.region, listings: [], orders: [] }
      s.orders.push(o)
      map.set(s.key, s)
    }
    return [...map.values()].sort((a, b) => b.orders.length - a.orders.length)
  }, [listings, orders])

  return (
    <div>
      <PageHeader title={t('nav.suppliers')} subtitle={t('suppliers.subtitle')} />
      {loading && !listings ? (
        <Loading />
      ) : error ? (
        <ErrorState text={errorText(error)} onRetry={reload} />
      ) : !suppliers.length ? (
        <Card>
          <EmptyState icon={Users} title={t('suppliers.none')} />
        </Card>
      ) : (
        <Card padded={false}>
          <ul className="divide-y divide-line">
            {suppliers.map((s) => {
              const confirmed = s.orders.filter((o) => o.status === 'SALE_CONFIRMED')
              return (
                <li key={s.key} className="px-4 py-4 sm:px-5">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <div className="font-semibold">{s.coop ?? s.name}</div>
                      <div className="text-[13px] text-muted">
                        {s.coop ? `${s.name} · ` : ''}
                        {s.farmerId} · {s.region}
                      </div>
                    </div>
                    {confirmed.length > 0 && <Badge tone="green">{t('suppliers.bought', { count: confirmed.length })}</Badge>}
                  </div>
                  {s.listings.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {s.listings.map((l) => (
                        <Link key={l.batch_id} to={`/market/${l.batch_id}`} className="inline-flex min-h-9 items-center gap-2 rounded-md border border-line px-3 text-[13px] hover:bg-sunken">
                          {t(`crops.${l.crop_type}`)} · <span className="num">{f.kg(l.available_kg)}</span> · <span className="num">{f.tzs(l.price_per_kg)}/kg</span>
                        </Link>
                      ))}
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
        </Card>
      )}
    </div>
  )
}

export function PaymentsPage() {
  const { t } = useTranslation()
  const f = useFormat()
  const { data: orders, loading } = useApi<Order[]>('/orders')
  const paid = (orders ?? []).filter((o) => o.payment_ref)
  const due = (orders ?? []).filter((o) => o.status === 'ACCEPTED')
  return (
    <div>
      <PageHeader title={t('nav.payments')} subtitle={t('payments.subtitle')} actions={<SimulatedTag label={t('payments.simulated')} />} />
      <StatStrip cols={3}>
        <Stat label={t('payments.paid')} value={f.tzs(paid.reduce((s, o) => s + o.total, 0))} sub={t('payments.count', { count: paid.length })} />
        <Stat label={t('payments.due')} value={f.tzs(due.reduce((s, o) => s + o.total, 0))} sub={t('payments.count', { count: due.length })} tone={due.length ? 'amber' : undefined} />
        <Stat label={t('payments.method')} value={t('payments.mobileMoney')} sub={t('payments.escrowNote')} />
      </StatStrip>
      <Card className="mt-5" padded={false}>
        {loading && !orders ? (
          <div className="p-4">
            <Loading rows={2} />
          </div>
        ) : ![...due, ...paid].length ? (
          <EmptyState icon={Wallet} title={t('payments.none')} />
        ) : (
          <ul className="divide-y divide-line">
            {[...due, ...paid].map((o) => (
              <li key={o.id} className="flex flex-wrap items-center gap-3 px-4 py-3 sm:px-5">
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium">
                    {o.farmer.display_name} · {t(`crops.${o.crop_type}`)} {f.kg(o.quantity_kg)}
                  </div>
                  <div className="text-xs text-muted">
                    {o.payment_ref ? <span className="num font-mono">{o.payment_ref}</span> : t('payments.awaiting')} · {f.date(o.updated_at)}
                  </div>
                </div>
                <span className="num font-semibold">{f.tzs(o.total)}</span>
                {o.payment_ref ? <Badge tone="green">{t('payments.paidBadge')}</Badge> : <Link to="/orders" className="text-sm font-medium text-forest-800">{t('payments.payNow')}</Link>}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
