import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from './ui'

/** Step-up confirmation: consent grants, loan requests and large orders need the PIN. */
export function PinDialog({ open, title, description, onConfirm, onCancel, busy }: {
  open: boolean
  title: string
  description?: string
  busy?: boolean
  onConfirm: (pin: string) => void
  onCancel: () => void
}) {
  const { t } = useTranslation()
  const [pin, setPin] = useState('')
  if (!open) return null
  const submit = (e: FormEvent) => {
    e.preventDefault()
    onConfirm(pin)
    setPin('')
  }
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-4 sm:items-center" role="dialog" aria-modal="true">
      <form onSubmit={submit} className="w-full max-w-sm rounded-2xl bg-white p-5 shadow-xl">
        <h3 className="text-lg font-semibold">🔒 {title}</h3>
        {description && <p className="mt-1 text-sm text-stone-600">{description}</p>}
        <label className="mt-4 block">
          <span className="label">{t('auth.pin')}</span>
          <input
            className="input text-center text-2xl tracking-[0.5em]"
            type="password"
            inputMode="numeric"
            autoComplete="current-password"
            pattern="[0-9]{4,6}"
            maxLength={6}
            autoFocus
            value={pin}
            onChange={(e) => setPin(e.target.value.replace(/\D/g, ''))}
          />
        </label>
        <p className="mt-2 text-xs text-stone-500">{t('pin.sharedPhoneHint')}</p>
        <div className="mt-4 flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onCancel}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" busy={busy} disabled={pin.length < 4}>
            {t('common.confirm')}
          </Button>
        </div>
      </form>
    </div>
  )
}
