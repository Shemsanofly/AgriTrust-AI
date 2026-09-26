import { ArrowRight, Store } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { CropImage } from '../../components/crops'
import { Badge, Card, EmptyState, ErrorState, Loading, PageHeader, Stat, StatStrip, Tabs } from '../../components/ui'
import { useApi, useErrorText, useFormat } from '../../lib/hooks'
import type { Batch } from '../farmer/shared'
import { OrderList, useOrders, type Order } from './OrderList'

const OPEN = ['REQUESTED', 'ACCEPTED', 'PAID', 'RELEASED', 'DELIVERED']

function split(orders: Order[]) {
  return { open: orders.filter((o) => OPEN.includes(o.status)), done: orders.filter((o) => !OPEN.includes(o.status)) }
}

/** Farmer "Market": buyer requests on my stock + what I have listed. */
export function FarmerMarketPage() {
  const { t } = useTranslation()
  const f = useFormat()
  const errorText = useErrorText()
  const { data: orders, loading, error, reload } = useOrders()
  const { data: batches } = useApi<Batch[]>('/batches')
  const [tab, setTab] = useState<'orders' | 'listings' | 'history'>('orders')
  const { open, done } = split(orders ?? [])
  const listed = (batches ?? []).filter((b) => b.listed)
  const sold = (orders ?? []).filter((o) => o.status === 'SALE_CONFIRMED')

  return (
    <div>
      <PageHeader title={t('market.farmerTitle')} subtitle={t('market.farmerSubtitle')} />
      <StatStrip cols={3}>
        <Stat label={t('market.openRequests')} value={open.length} sub={open.some((o) => o.status === 'REQUESTED') ? t('market.needsReply') : t('market.upToDate')} tone={open.some((o) => o.status === 'REQUESTED') ? 'amber' : undefined} />
        <Stat label={t('market.listedStock')} value={f.kg(listed.reduce((s, b) => s + b.available_kg, 0))} sub={t('ghala.batchCount', { count: listed.length })} />
        <Stat label={t('market.verifiedSales')} value={f.tzs(sold.reduce((s, o) => s + o.total, 0))} sub={t('market.salesCount', { count: sold.length })} />
      </StatStrip>
      <div className="mt-5">
        <Tabs
          value={tab}
          onChange={setTab}
          tabs={[
            { id: 'orders', label: t('market.requests'), count: open.length },
            { id: 'listings', label: t('market.myListings'), count: listed.length },
            { id: 'history', label: t('market.history'), count: done.length },
          ]}
        />
      </div>
      <div className="mt-4">
        {loading && !orders ? (
          <Loading />
        ) : error ? (
          <ErrorState text={errorText(error)} onRetry={reload} />
        ) : tab === 'orders' ? (
          <OrderList orders={open} onChanged={reload} emptyTitle={t('market.noRequests')} emptyBody={t('market.noRequestsBody')} />
        ) : tab === 'history' ? (
          <OrderList orders={done} onChanged={reload} emptyTitle={t('market.noHistory')} />
        ) : (
          <Card padded={false}>
            {!listed.length ? (
              <EmptyState
                icon={Store}
                title={t('market.nothingListed')}
                body={t('market.nothingListedBody')}
                action={
                  <Link to="/ghala" className="inline-flex min-h-11 items-center gap-2 rounded-md bg-forest-800 px-4 text-sm font-medium text-white">
                    {t('nav.ghala')} <ArrowRight className="size-4" aria-hidden />
                  </Link>
                }
              />
            ) : (
              <ul className="divide-y divide-line">
                {listed.map((b) => (
                  <li key={b.id}>
                    <Link to={`/ghala/${b.id}`} className="flex items-center gap-3 px-4 py-3 hover:bg-sunken/60 sm:px-5">
                      <CropImage crop={b.crop_type} className="size-12" />
                      <div className="min-w-0 flex-1">
                        <div className="font-medium">
                          {t(`crops.${b.crop_type}`)} · {t('ghala.gradeX', { grade: b.grade })}
                        </div>
                        <div className="num text-[13px] text-muted">
                          {f.kg(b.available_kg)} · {b.warehouse?.name}
                        </div>
                      </div>
                      <div className="num text-right">
                        <div className="font-semibold">{f.tzs(b.price_per_kg)}</div>
                        <div className="text-xs text-muted">/ kg</div>
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        )}
      </div>
    </div>
  )
}

export function BuyerOrdersPage() {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const { data, loading, error, reload } = useOrders()
  const [tab, setTab] = useState<'open' | 'done'>('open')
  const { open, done } = split(data ?? [])
  return (
    <div>
      <PageHeader title={t('nav.myOrders')} subtitle={t('orders.buyerSubtitle')} />
      <Tabs
        value={tab}
        onChange={setTab}
        tabs={[
          { id: 'open', label: t('orders.inProgress'), count: open.length },
          { id: 'done', label: t('orders.completed'), count: done.length },
        ]}
      />
      <div className="mt-4">
        {loading && !data ? (
          <Loading />
        ) : error ? (
          <ErrorState text={errorText(error)} onRetry={reload} />
        ) : (
          <OrderList
            orders={tab === 'open' ? open : done}
            onChanged={reload}
            emptyTitle={tab === 'open' ? t('orders.noneOpen') : t('orders.noneDone')}
            emptyBody={tab === 'open' ? t('orders.noneOpenBody') : undefined}
          />
        )}
      </div>
    </div>
  )
}

export function WarehouseOrdersPage() {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const { data, loading, error, reload } = useOrders()
  const toRelease = (data ?? []).filter((o) => o.status === 'PAID')
  const other = (data ?? []).filter((o) => o.status !== 'PAID')
  return (
    <div className="space-y-5">
      <PageHeader title={t('nav.releases')} subtitle={t('orders.warehouseSubtitle')} actions={toRelease.length > 0 && <Badge tone="gold">{t('orders.toRelease', { count: toRelease.length })}</Badge>} />
      {loading && !data ? (
        <Loading />
      ) : error ? (
        <ErrorState text={errorText(error)} onRetry={reload} />
      ) : (
        <>
          <OrderList orders={toRelease} onChanged={reload} emptyTitle={t('orders.nothingToRelease')} emptyBody={t('orders.nothingToReleaseBody')} />
          {other.length > 0 && (
            <section>
              <h2 className="mb-2.5 text-[15px] font-semibold">{t('orders.otherOrders')}</h2>
              <OrderList orders={other} onChanged={reload} emptyTitle="" />
            </section>
          )}
        </>
      )}
    </div>
  )
}
