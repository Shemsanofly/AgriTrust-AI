import { Check, MessageSquare, Phone, ShieldCheck, Smartphone } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { ConfirmAction } from '../../components/ConfirmAction'
import { CropImage } from '../../components/crops'
import { Badge, Button, Card, EmptyState, ErrorNote, SimulatedTag, StatusBadge, cx, useToast } from '../../components/ui'
import { ApiError, api } from '../../lib/api'
import { useApi, useErrorText, useFormat } from '../../lib/hooks'
import { PayDialog } from './PayDialog'

export type Payment = {
  id: number
  provider: 'simulated' | 'snippe'
  reference: string | null
  amount: number
  phone: string
  status: 'PENDING' | 'COMPLETED' | 'FAILED' | 'EXPIRED' | 'VOIDED'
  failure_reason: string | null
  created_at: string
} | null

export type Order = {
  id: number
  batch_id: string
  quantity_kg: number
  price_per_kg: number
  total: number
  status: string
  payment_ref: string | null
  created_at: string
  updated_at: string
  crop_type: string
  grade: string | null
  farmer: { public_id: string; display_name: string; region: string; phone: string | null }
  buyer: { business_name: string; country: string; phone: string | null }
  warehouse: { name: string; region: string } | null
  sale: { id: string; confirmed_by_farmer_at: string | null; confirmed_by_buyer_at: string | null; completed_at: string | null } | null
  my_role: 'farmer' | 'buyer' | 'warehouse' | 'admin'
  payment: Payment
  payment_mode: 'simulated' | 'snippe'
}

const FLOW = ['REQUESTED', 'ACCEPTED', 'PAID', 'RELEASED', 'DELIVERED', 'SALE_CONFIRMED']
const STEP_UP_TZS = 500_000

export function OrderList({ orders, onChanged, emptyTitle, emptyBody }: { orders: Order[]; onChanged: () => void; emptyTitle: string; emptyBody?: string }) {
  if (!orders.length)
    return (
      <Card>
        <EmptyState icon={ShieldCheck} title={emptyTitle} body={emptyBody} />
      </Card>
    )
  return (
    <div className="space-y-3">
      {orders.map((o) => (
        <OrderCard key={o.id} order={o} onChanged={onChanged} />
      ))}
    </div>
  )
}

function OrderCard({ order, onChanged }: { order: Order; onChanged: () => void }) {
  const { t } = useTranslation()
  const f = useFormat()
  const toast = useToast()
  const errorText = useErrorText()
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [confirming, setConfirming] = useState<string | null>(null)
  const [chatOpen, setChatOpen] = useState(false)
  const [paying, setPaying] = useState(false)
  const role = order.my_role
  const live = order.payment?.provider === 'snippe'
  const payPending = live && order.payment?.status === 'PENDING'

  const act = async (action: string, pin?: string) => {
    setBusy(action)
    setError(null)
    try {
      if (action === 'confirm') await api(`/sales/${order.sale!.id}/confirm`, { method: 'POST' })
      else await api(`/orders/${order.id}`, { method: 'PATCH', body: { action, confirm_pin: pin } })
      toast(t(`orders.done.${action}`))
      onChanged()
    } catch (err) {
      if (err instanceof ApiError && err.code === 'step_up_required' && !pin) setConfirming(action)
      else setError(errorText(err))
      if (pin) throw err
    } finally {
      setBusy(null)
    }
  }

  const start = (action: string) => {
    if (action === 'pay' && order.payment_mode === 'snippe') return setPaying(true)
    return action === 'pay' && order.total > STEP_UP_TZS ? setConfirming(action) : act(action)
  }

  const actions: { id: string; label: string; variant?: 'primary' | 'secondary' | 'danger' }[] = []
  if (role === 'farmer' && order.status === 'REQUESTED') actions.push({ id: 'accept', label: t('orders.accept') }, { id: 'decline', label: t('orders.decline'), variant: 'secondary' })
  if (role === 'buyer' && order.status === 'ACCEPTED') actions.push({ id: 'pay', label: payPending ? t('pay.checkPayment') : t('orders.pay', { amount: f.tzs(order.total) }) })
  if (role === 'warehouse' && order.status === 'PAID') actions.push({ id: 'release', label: t('orders.release', { kg: f.kg(order.quantity_kg) }) })
  if (role === 'buyer' && order.status === 'RELEASED') actions.push({ id: 'deliver', label: t('orders.deliver') })
  if (order.sale && !order.sale.completed_at) {
    const mine = role === 'farmer' ? order.sale.confirmed_by_farmer_at : role === 'buyer' ? order.sale.confirmed_by_buyer_at : 'n/a'
    if (!mine) actions.push({ id: 'confirm', label: t('orders.confirmSale') })
  }
  if ((role === 'farmer' || role === 'buyer') && ['REQUESTED', 'ACCEPTED'].includes(order.status)) actions.push({ id: 'cancel', label: t('orders.cancel'), variant: 'danger' })

  const step = FLOW.indexOf(order.status)
  const waitingOn = nextParty(order)
  const counterpart = role === 'buyer' ? order.farmer.display_name : order.buyer.business_name
  const counterpartPhone = role === 'buyer' ? order.farmer.phone : role === 'farmer' ? order.buyer.phone : null

  return (
    <Card as="article" padded={false}>
      <div className="flex gap-3 p-4 sm:p-5">
        <CropImage crop={order.crop_type} className="size-14 shrink-0" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold">
              {t(`crops.${order.crop_type}`)} · {f.kg(order.quantity_kg)}
            </span>
            <StatusBadge status={order.status} />
          </div>
          <p className="mt-0.5 text-[13px] text-muted">
            {t('orders.number', { id: order.id })} · {counterpart}
            {role === 'warehouse' && ` → ${order.buyer.business_name}`} · {f.date(order.created_at)}
          </p>
          <p className="num mt-1 text-sm">
            {f.tzs(order.price_per_kg)}/kg · <span className="font-semibold">{f.tzs(order.total)}</span>
          </p>
        </div>
      </div>

      {step >= 0 && (
        <div className="border-t border-line px-4 py-3 sm:px-5">
          <ol className="flex gap-1" aria-label={t('orders.progress')}>
            {FLOW.map((s, i) => (
              <li key={s} className="min-w-0 flex-1" aria-current={i === step ? 'step' : undefined}>
                <div className={cx('h-1 rounded-full', i <= step ? 'bg-forest-700' : 'bg-line')} />
                <div className={cx('mt-1 hidden truncate text-[11px] sm:block', i === step ? 'font-semibold text-ink' : 'text-muted')}>{t(`status.${s}`)}</div>
              </li>
            ))}
          </ol>
          {waitingOn && (
            <p className="mt-2 text-[13px] text-ink-soft">
              {waitingOn === role ? <span className="font-medium text-harvest-800">{t('orders.yourTurn')}</span> : t(`orders.waitingOn.${waitingOn}`)}
            </p>
          )}
          {order.sale && (
            <p className="mt-1 flex flex-wrap items-center gap-3 text-xs text-muted">
              <span className="flex items-center gap-1">
                {order.sale.confirmed_by_farmer_at ? <Check className="size-3.5 text-forest-700" aria-hidden /> : '○'} {t('roles.FARMER')}
              </span>
              <span className="flex items-center gap-1">
                {order.sale.confirmed_by_buyer_at ? <Check className="size-3.5 text-forest-700" aria-hidden /> : '○'} {t('roles.BUYER')}
              </span>
              {order.sale.completed_at && (
                <Link to={`/verify/${order.sale.id}`} className="flex items-center gap-1 font-medium text-forest-800">
                  <ShieldCheck className="size-3.5" aria-hidden /> {t('orders.verifiedSale', { id: order.sale.id })}
                </Link>
              )}
            </p>
          )}
          {payPending && (
            <p className="mt-1 flex items-center gap-1.5 text-xs text-harvest-800">
              <Smartphone className="size-3.5" aria-hidden /> {t('pay.pendingLine', { phone: order.payment!.phone })}
            </p>
          )}
          {order.payment_ref && (
            <p className="mt-1 flex items-center gap-2 text-xs text-muted">
              {t('orders.paymentRef')}: <span className="num font-mono">{order.payment_ref}</span> {live ? <Badge tone="green">{t('pay.viaSnippe')}</Badge> : <SimulatedTag />}
            </p>
          )}
        </div>
      )}

      {(actions.length > 0 || role === 'farmer' || role === 'buyer') && (
        <div className="flex flex-wrap items-center gap-2 border-t border-line px-4 py-3 sm:px-5">
          {actions.map((a) => (
            <Button key={a.id} size="sm" variant={a.variant ?? 'primary'} busy={busy === a.id} onClick={() => start(a.id)}>
              {a.label}
            </Button>
          ))}
          <span className="flex-1" />
          {counterpartPhone && (
            <a href={`tel:${counterpartPhone}`} className="inline-flex min-h-9 items-center gap-1.5 rounded-md px-2 text-[13px] text-forest-800 hover:bg-forest-50">
              <Phone className="size-4" aria-hidden /> {counterpartPhone}
            </a>
          )}
          {(role === 'farmer' || role === 'buyer') && (
            <Button size="sm" variant="ghost" icon={MessageSquare} onClick={() => setChatOpen((v) => !v)} aria-expanded={chatOpen}>
              {t('orders.messages')}
            </Button>
          )}
        </div>
      )}
      {error && (
        <div className="px-4 pb-3 sm:px-5">
          <ErrorNote text={error} />
        </div>
      )}
      {chatOpen && <Chat orderId={order.id} />}
      {paying && <PayDialog order={order} open={paying} onClose={() => (setPaying(false), onChanged())} onPaid={() => (setPaying(false), onChanged())} />}
      <ConfirmAction
        open={confirming != null}
        title={t('orders.confirmPaymentTitle')}
        summary={[
          [t('orders.payTo'), order.farmer.display_name],
          [t('orders.amount'), f.tzs(order.total)],
          [t('orders.for'), `${t(`crops.${order.crop_type}`)} · ${f.kg(order.quantity_kg)} · ${order.batch_id}`],
        ]}
        note={t('orders.paymentSimulated')}
        confirmLabel={t('orders.payNow')}
        onClose={() => setConfirming(null)}
        onConfirm={(pin) => act(confirming!, pin)}
      />
    </Card>
  )
}

function nextParty(o: Order): Order['my_role'] | null {
  switch (o.status) {
    case 'REQUESTED':
      return 'farmer'
    case 'ACCEPTED':
    case 'RELEASED':
      return 'buyer'
    case 'PAID':
      return 'warehouse'
    case 'DELIVERED':
      if (o.sale && !o.sale.confirmed_by_buyer_at) return 'buyer'
      if (o.sale && !o.sale.confirmed_by_farmer_at) return 'farmer'
      return null
    default:
      return null
  }
}

function Chat({ orderId }: { orderId: number }) {
  const { t } = useTranslation()
  const f = useFormat()
  const { data, reload } = useApi<{ id: number; body: string; mine: boolean; sender_name: string; created_at: string }[]>(`/orders/${orderId}/messages`)
  const [text, setText] = useState('')
  const send = async (e: FormEvent) => {
    e.preventDefault()
    if (!text.trim()) return
    await api(`/orders/${orderId}/messages`, { method: 'POST', body: { body: text.trim() } })
    setText('')
    reload()
  }
  return (
    <div className="border-t border-line bg-sunken/50 px-4 py-3 sm:px-5">
      <div className="max-h-64 space-y-2 overflow-y-auto">
        {!data?.length && <p className="py-2 text-center text-xs text-muted">{t('orders.noMessages')}</p>}
        {data?.map((m) => (
          <div key={m.id} className={cx('max-w-[85%] rounded-lg px-3 py-2 text-sm', m.mine ? 'ml-auto bg-forest-800 text-white' : 'bg-surface')}>
            <div>{m.body}</div>
            <div className={cx('mt-0.5 text-[10px]', m.mine ? 'text-white/70' : 'text-muted')}>
              {m.sender_name} · {f.time(m.created_at)}
            </div>
          </div>
        ))}
      </div>
      <form onSubmit={send} className="mt-2 flex gap-2">
        <input className="input" value={text} onChange={(e) => setText(e.target.value)} placeholder={t('orders.typeMessage')} aria-label={t('orders.typeMessage')} />
        <Button type="submit" disabled={!text.trim()}>
          {t('orders.send')}
        </Button>
      </form>
    </div>
  )
}

export function useOrders() {
  return useApi<Order[]>('/orders')
}

