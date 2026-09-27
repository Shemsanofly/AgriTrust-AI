import { CheckCircle2, Smartphone, XCircle } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { PhoneInput } from '../../components/PhoneInput'
import { Button, Dialog, ErrorNote, Field, KeyValues, Notice, useToast } from '../../components/ui'
import { ApiError, api } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { useErrorText, useFormat } from '../../lib/hooks'
import type { Order, Payment } from './OrderList'

const STEP_UP_TZS = 500_000
/** Snippe's smallest mobile-money payment. */
const MIN_TZS = 500
/** Same rule as the server: something@domain.tld, no spaces. */
export const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/
const POLL_MS = 4000
const GIVE_UP_MS = 3 * 60_000

/** Live mobile-money payment through Snippe: the payer approves a USSD prompt on their
 * phone, and the order becomes Paid only once Snippe confirms. */
export function PayDialog({ order, open, onClose, onPaid }: { order: Order; open: boolean; onClose: () => void; onPaid: () => void }) {
  const { t } = useTranslation()
  const f = useFormat()
  const toast = useToast()
  const errorText = useErrorText()
  const { user } = useAuth()
  const pending = order.payment?.provider === 'snippe' && order.payment.status === 'PENDING'
  const [step, setStep] = useState<'form' | 'waiting' | 'failed'>(pending ? 'waiting' : 'form')
  const [phone, setPhone] = useState(user?.phone ?? '')
  const [email, setEmail] = useState(user?.email ?? '')
  const [pin, setPin] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [payment, setPayment] = useState<Payment | null>(order.payment)
  const [slow, setSlow] = useState(false)
  const needsPin = order.total > STEP_UP_TZS
  const tooSmall = Math.ceil(order.total) < MIN_TZS
  const started = useRef(0)
  // Snippe's reasons are English API messages; translate the ones payers commonly hit.
  const explain = (reason: string) => (/unsupported mobile carrier/i.test(reason) ? t('pay.reasons.carrier') : /insufficient/i.test(reason) ? t('pay.reasons.balance') : reason)

  useEffect(() => {
    if (open) setStep(pending ? 'waiting' : 'form')
  }, [open, pending])

  // While waiting, ask the server every few seconds (it re-checks with Snippe).
  useEffect(() => {
    if (!open || step !== 'waiting') return
    started.current = Date.now()
    setSlow(false)
    let stop = false
    const tick = async () => {
      try {
        const res = await api<{ payment: Payment; order: Order }>(`/orders/${order.id}/payment`)
        if (stop) return
        setPayment(res.payment)
        if (res.payment?.status === 'COMPLETED') {
          toast(t('pay.paid', { amount: f.tzs(order.total) }))
          onPaid()
          return
        }
        if (res.payment && res.payment.status !== 'PENDING') return setStep('failed')
      } catch {
        /* network hiccup: keep trying */
      }
      if (Date.now() - started.current > GIVE_UP_MS) setSlow(true)
      if (!stop) timer = window.setTimeout(tick, POLL_MS)
    }
    let timer = window.setTimeout(tick, POLL_MS)
    return () => {
      stop = true
      window.clearTimeout(timer)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, step, order.id])

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!phone) return setError(t('validation.phone'))
    if (!EMAIL.test(email.trim())) return setError(t('pay.emailInvalid'))
    if (needsPin && pin.length < 4) return setError(t('validation.pin'))
    setBusy(true)
    setError(null)
    try {
      const res = await api<Order>(`/orders/${order.id}`, { method: 'PATCH', body: { action: 'pay', phone, email: email.trim(), confirm_pin: needsPin ? pin : undefined } })
      setPayment(res.payment)
      setStep('waiting')
    } catch (err) {
      if (err instanceof ApiError && err.code === 'payment_pending') setStep('waiting')
      else if (err instanceof ApiError && err.code === 'payment_provider_error' && typeof err.details.reason === 'string') setError(t('pay.refused', { reason: explain(err.details.reason) }))
      else setError(errorText(err))
    } finally {
      setBusy(false)
      setPin('')
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title={t('pay.title')}>
      {step === 'form' && (
        <form onSubmit={submit} className="space-y-4" noValidate>
          <KeyValues
            items={[
              [t('orders.payTo'), order.farmer.display_name],
              [t('orders.amount'), <span className="num">{f.tzs(Math.ceil(order.total))}</span>],
              [t('orders.for'), `${t(`crops.${order.crop_type}`)} · ${f.kg(order.quantity_kg)} · ${order.batch_id}`],
            ]}
          />
          <Field label={t('pay.phone')} hint={t('pay.phoneHint')}>
            <PhoneInput label={t('pay.phone')} value={phone} onChange={setPhone} />
          </Field>
          <Field label={t('pay.email')} hint={t('pay.emailHint')}>
            <input className="input" type="email" inputMode="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="jina@mfano.co.tz" />
          </Field>
          {needsPin && (
            <Field label={t('pay.appPin')}>
              <input className="input tracking-[0.3em]" type="password" inputMode="numeric" autoComplete="current-password" maxLength={6} value={pin} onChange={(e) => setPin(e.target.value.replace(/\D/g, ''))} />
            </Field>
          )}
          {tooSmall ? <Notice tone="danger">{t('pay.tooSmall', { min: f.tzs(MIN_TZS) })}</Notice> : <Notice tone="warning">{t('pay.liveNote')}</Notice>}
          <ErrorNote text={error} />
          <Button type="submit" busy={busy} disabled={tooSmall} icon={Smartphone} className="w-full">
            {t('pay.send', { amount: f.tzs(Math.ceil(order.total)) })}
          </Button>
        </form>
      )}

      {step === 'waiting' && (
        <div className="space-y-4 py-2 text-center">
          <span className="mx-auto flex size-16 items-center justify-center rounded-full bg-forest-50 text-forest-800">
            <Smartphone className="size-8 animate-pulse" aria-hidden />
          </span>
          <div>
            <p className="font-semibold">{t('pay.checkPhone')}</p>
            <p className="mt-1 text-sm text-muted">{t('pay.approveOn', { phone: payment?.phone ?? phone, amount: f.tzs(payment?.amount ?? Math.ceil(order.total)) })}</p>
          </div>
          <p className="text-xs text-muted" role="status" aria-live="polite">
            {slow ? t('pay.slow') : t('pay.waiting')}
          </p>
          {payment?.reference && <p className="num font-mono text-xs text-muted">{payment.reference}</p>}
          <Button variant="secondary" onClick={onClose}>
            {t('pay.later')}
          </Button>
        </div>
      )}

      {step === 'failed' && (
        <div className="space-y-4 py-2 text-center">
          <span className="mx-auto flex size-16 items-center justify-center rounded-full bg-danger-100 text-danger-700">
            <XCircle className="size-8" aria-hidden />
          </span>
          <div>
            <p className="font-semibold">{t(`pay.status.${payment?.status ?? 'FAILED'}`)}</p>
            {payment?.failure_reason && <p className="mt-1 text-sm text-muted">{payment.failure_reason}</p>}
          </div>
          <div className="flex justify-center gap-2">
            <Button variant="ghost" onClick={onClose}>
              {t('common.close')}
            </Button>
            <Button icon={CheckCircle2} onClick={() => (setError(null), setStep('form'))}>
              {t('pay.tryAgain')}
            </Button>
          </div>
        </div>
      )}
    </Dialog>
  )
}
