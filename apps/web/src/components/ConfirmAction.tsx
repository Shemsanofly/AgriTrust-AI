import { Fingerprint, KeyRound, Lock } from 'lucide-react'
import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { ApiError } from '../lib/api'
import { useAuth } from '../lib/auth'
import { biometricAvailable, biometricConfirm } from '../lib/biometric'
import { useErrorText } from '../lib/hooks'
import { Button, Dialog, ErrorNote, KeyValues } from './ui'

/** Confirms a sensitive action (sharing data, applying for a loan, a large order or
 * payment). Device biometric first where available; PIN always works. `onConfirm`
 * receives the value to send as `confirm_pin`. */
export function ConfirmAction({
  open,
  title,
  summary,
  note,
  confirmLabel,
  onConfirm,
  onClose,
}: {
  open: boolean
  title: string
  summary?: [ReactNode, ReactNode][]
  note?: ReactNode
  confirmLabel?: string
  onConfirm: (confirmPin: string) => Promise<unknown>
  onClose: () => void
}) {
  const { t } = useTranslation()
  const { hasPasskey } = useAuth()
  const errorText = useErrorText()
  const [pin, setPin] = useState('')
  const [busy, setBusy] = useState<'pin' | 'bio' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [bioReady, setBioReady] = useState(false)

  useEffect(() => {
    if (!open) return
    setPin('')
    setError(null)
    biometricAvailable().then((ok) => setBioReady(ok && hasPasskey))
  }, [open, hasPasskey])

  const run = async (kind: 'pin' | 'bio', getPin: () => Promise<string>) => {
    setBusy(kind)
    setError(null)
    try {
      await onConfirm(await getPin())
      onClose()
    } catch (err) {
      if (err instanceof ApiError) setError(errorText(err))
      else if (kind === 'bio') setError(t('security.biometricCancelled'))
      else setError(errorText(err))
      setPin('')
    } finally {
      setBusy(null)
    }
  }

  const submit = (e: FormEvent) => {
    e.preventDefault()
    run('pin', async () => pin)
  }

  return (
    <Dialog open={open} onClose={onClose} title={title}>
      {summary && (
        <div className="mb-4 rounded-md bg-sunken p-3.5">
          <KeyValues items={summary} cols={1} />
        </div>
      )}
      {note && <p className="mb-4 text-[13px] text-muted">{note}</p>}
      {bioReady && (
        <>
          <Button size="lg" className="w-full" icon={Fingerprint} busy={busy === 'bio'} data-autofocus onClick={() => run('bio', biometricConfirm)}>
            {t('security.confirmWithBiometric')}
          </Button>
          <div className="my-4 flex items-center gap-3 text-xs text-muted">
            <span className="h-px flex-1 bg-line" />
            {t('security.orPin')}
            <span className="h-px flex-1 bg-line" />
          </div>
        </>
      )}
      <form onSubmit={submit}>
        <label className="block">
          <span className="label flex items-center gap-1.5">
            <Lock className="size-3.5" aria-hidden /> {t('auth.pin')}
          </span>
          <input
            className="input text-center text-2xl tracking-[0.5em]"
            type="password"
            inputMode="numeric"
            autoComplete="off"
            maxLength={6}
            value={pin}
            aria-invalid={Boolean(error)}
            onChange={(e) => setPin(e.target.value.replace(/\D/g, ''))}
          />
        </label>
        <p className="mt-2 text-xs text-muted">{t('pin.sharedPhoneHint')}</p>
        <div className="mt-3">
          <ErrorNote text={error} />
        </div>
        <div className="mt-4 flex gap-2">
          <Button variant="secondary" className="flex-1" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" className="flex-1" icon={KeyRound} busy={busy === 'pin'} disabled={pin.length < 4}>
            {confirmLabel ?? t('common.confirm')}
          </Button>
        </div>
      </form>
    </Dialog>
  )
}
