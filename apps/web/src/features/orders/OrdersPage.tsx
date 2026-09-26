import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { PinDialog } from '../../components/PinDialog'
import { Button, Card, Empty, ErrorNote, Loading, SimulatedTag, StatusBadge } from '../../components/ui'
import { ApiError, api } from '../../lib/api'
import { useApi, useErrorText, useFormat } from '../../lib/hooks'

type Order = {
  id: number
  batch_id: string
  quantity_kg: number
  price_per_kg: number
  total: number
  status: string
  payment_ref: string | null
  created_at: string
  crop_type: string
  grade: string | null
  farmer: { display_name: string; region: string; phone: string | null }
  buyer: { business_name: string; country: string; phone: string | null }
  warehouse: { name: string } | null
  sale: { id: string; confirmed_by_farmer_at: string | null; confirmed_by_buyer_at: string | null; completed_at: string | null } | null
  my_role: 'farmer' | 'buyer' | 'warehouse' | 'admin'
}

const FLOW = ['REQUESTED', 'ACCEPTED', 'PAID', 'RELEASED', 'DELIVERED', 'SALE_CONFIRMED']

export function OrdersPage() {
  const { t } = useTranslation()
  const { data, loading, reload } = useApi<Order[]>('/orders')
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">📦 {t('orders.title')}</h1>
      {loading && !data ? <Loading /> : !data?.length ? <Empty>{t('orders.none')}</Empty> : data.map((o) => <OrderCard key={o.id} order={o} onChanged={reload} />)}
    </div>
  )
}

function OrderCard({ order, onChanged }: { order: Order; onChanged: () => void }) {
  const { t } = useTranslation()
  const f = useFormat()
  const errorText = useErrorText()
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pinFor, setPinFor] = useState<string | null>(null)
  const [chatOpen, setChatOpen] = useState(false)
  const role = order.my_role

  const act = async (action: string, pin?: string) => {
    setBusy(action)
    setError(null)
    try {
      if (action === 'confirm') await api(`/sales/${order.sale!.id}/confirm`, { method: 'POST' })
      else await api(`/orders/${order.id}`, { method: 'PATCH', body: { action, confirm_pin: pin } })
      setPinFor(null)
      onChanged()
    } catch (err) {
      if (err instanceof ApiError && err.code === 'step_up_required' && !pin) setPinFor(action)
      else setError(errorText(err))
    } finally {
      setBusy(null)
    }
  }

  const actions: { id: string; label: string; variant?: 'primary' | 'secondary' | 'danger' }[] = []
  if (role === 'farmer' && order.status === 'REQUESTED') actions.push({ id: 'accept', label: t('orders.accept') }, { id: 'decline', label: t('orders.decline'), variant: 'secondary' })
  if (role === 'buyer' && order.status === 'ACCEPTED') actions.push({ id: 'pay', label: t('orders.pay') })
  if (role === 'warehouse' && order.status === 'PAID') actions.push({ id: 'release', label: t('orders.release') })
  if (role === 'buyer' && order.status === 'RELEASED') actions.push({ id: 'deliver', label: t('orders.deliver') })
  if (order.sale && !order.sale.completed_at) {
    const mine = role === 'farmer' ? order.sale.confirmed_by_farmer_at : role === 'buyer' ? order.sale.confirmed_by_buyer_at : 'n/a'
    if (!mine) actions.push({ id: 'confirm', label: t('orders.confirmSale') })
  }
  if ((role === 'farmer' || role === 'buyer') && ['REQUESTED', 'ACCEPTED'].includes(order.status)) actions.push({ id: 'cancel', label: t('orders.cancel'), variant: 'secondary' })

  const step = FLOW.indexOf(order.status)

  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold">#{order.id}</span>
            <StatusBadge status={order.status} />
          </div>
          <p className="mt-1 text-sm">
            {t(`crops.${order.crop_type}`)} {order.grade && `· ${t('ghala.grade')} ${order.grade}`} ·{' '}
            <Link to={`/verify/${order.batch_id}`} className="font-mono text-brand-800 underline">
              {order.batch_id}
            </Link>
          </p>
          <p className="text-sm text-stone-600">
            {f.num(order.quantity_kg)} kg × {f.tzs(order.price_per_kg)} = <b>{f.tzs(order.total)}</b>
          </p>
          <p className="text-sm text-stone-600">
            {role === 'buyer' ? `👩🏾‍🌾 ${order.farmer.display_name} · ${order.farmer.region}` : `🧺 ${order.buyer.business_name} (${order.buyer.country})`}
            {role === 'buyer' && order.farmer.phone && ` · 📞 ${order.farmer.phone}`}
            {role === 'farmer' && order.buyer.phone && ` · 📞 ${order.buyer.phone}`}
          </p>
          {order.payment_ref && (
            <p className="text-xs text-stone-500">
              {t('orders.paymentRef')}: {order.payment_ref} <SimulatedTag />
            </p>
          )}
        </div>
        <span className="text-xs text-stone-500">{f.dateTime(order.created_at)}</span>
      </div>

      {step >= 0 && (
        <ol className="mt-3 flex gap-1" aria-label={t('orders.progress')}>
          {FLOW.map((s, i) => (
            <li key={s} className="flex-1">
              <div className={`h-1.5 rounded-full ${i <= step ? 'bg-brand-600' : 'bg-stone-200'}`} />
              <div className={`mt-1 hidden text-[10px] sm:block ${i <= step ? 'text-brand-800' : 'text-stone-400'}`}>{t(`status.${s}`)}</div>
            </li>
          ))}
        </ol>
      )}

      {order.sale && (
        <p className="mt-2 text-xs text-stone-600">
          {t('orders.confirmations')}: 👩🏾‍🌾 {order.sale.confirmed_by_farmer_at ? '✅' : '⏳'} · 🧺 {order.sale.confirmed_by_buyer_at ? '✅' : '⏳'}
          {order.sale.completed_at && (
            <>
              {' · '}
              <Link to={`/verify/${order.sale.id}`} className="text-brand-800 underline">
                {t('orders.verifiedSale')} {order.sale.id}
              </Link>
            </>
          )}
        </p>
      )}

      <div className="mt-3 flex flex-wrap gap-2">
        {actions.map((a) => (
          <Button key={a.id} variant={a.variant ?? 'primary'} busy={busy === a.id} onClick={() => act(a.id)}>
            {a.label}
          </Button>
        ))}
        {(role === 'farmer' || role === 'buyer') && (
          <Button variant="ghost" onClick={() => setChatOpen((v) => !v)}>
            💬 {t('orders.messages')}
          </Button>
        )}
      </div>
      <ErrorNote text={error} />
      {chatOpen && <Chat orderId={order.id} />}
      <PinDialog
        open={pinFor != null}
        busy={busy != null}
        title={t('pin.confirmPayment')}
        description={t('pin.largeOrder', { amount: f.tzs(order.total) })}
        onCancel={() => setPinFor(null)}
        onConfirm={(pin) => act(pinFor!, pin)}
      />
    </Card>
  )
}

function Chat({ orderId }: { orderId: number }) {
  const { t } = useTranslation()
  const f = useFormat()
  const { data, reload } = useApi<{ id: number; body: string; mine: boolean; sender_name: string; created_at: string }[]>(`/orders/${orderId}/messages`)
  const [text, setText] = useState('')
  const send = async (e: FormEvent) => {
    e.preventDefault()
    if (!text.trim()) return
    await api(`/orders/${orderId}/messages`, { method: 'POST', body: { body: text } })
    setText('')
    reload()
  }
  return (
    <div className="mt-3 rounded-xl bg-stone-50 p-3">
      <div className="max-h-64 space-y-2 overflow-y-auto">
        {!data?.length && <p className="text-center text-xs text-stone-500">{t('orders.noMessages')}</p>}
        {data?.map((m) => (
          <div key={m.id} className={`max-w-[80%] rounded-xl px-3 py-2 text-sm ${m.mine ? 'ml-auto bg-brand-700 text-white' : 'bg-white'}`}>
            <div>{m.body}</div>
            <div className={`mt-0.5 text-[10px] ${m.mine ? 'text-white/70' : 'text-stone-500'}`}>
              {m.sender_name} · {f.time(m.created_at)}
            </div>
          </div>
        ))}
      </div>
      <form onSubmit={send} className="mt-2 flex gap-2">
        <input className="input" value={text} onChange={(e) => setText(e.target.value)} placeholder={t('orders.typeMessage')} />
        <Button type="submit">{t('orders.send')}</Button>
      </form>
    </div>
  )
}
