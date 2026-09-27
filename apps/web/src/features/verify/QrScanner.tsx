import { Camera, CameraOff, ImageUp, Search } from 'lucide-react'
import QrScannerLib from 'qr-scanner'
import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { Button, Notice } from '../../components/ui'

/** Extracts a batch / receipt / sale id from a scanned QR (URL or bare id). */
export function idFromCode(raw: string): string | null {
  const m = raw.trim().match(/(BATCH-[A-Z0-9]+|WR-\d{4}-\d{6}|SALE-[A-Z0-9]+)/i)
  return m ? m[1].toUpperCase() : null
}

type Status = 'idle' | 'insecure' | 'noCamera' | 'denied' | 'noQr' | 'notOurs'

/** QR scanning with nimiq/qr-scanner: uses the browser's BarcodeDetector where it exists and
 * its own web-worker decoder elsewhere (iPhone Safari, Firefox). Browsers only open the camera
 * on HTTPS or localhost, so a photo of the code and typing the code always work too. */
export function QrScanner() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const videoRef = useRef<HTMLVideoElement>(null)
  const photoRef = useRef<HTMLInputElement>(null)
  const [active, setActive] = useState(false)
  const [status, setStatus] = useState<Status>('idle')
  const [code, setCode] = useState('')
  const [error, setError] = useState<string | null>(null)

  const open = (raw: string) => {
    const id = idFromCode(raw)
    if (!id) return false
    navigate(`/verify/${id}`)
    return true
  }

  useEffect(() => {
    if (!active || !videoRef.current) return
    let done = false
    const scanner = new QrScannerLib(
      videoRef.current,
      (result) => {
        if (done) return
        if (open(result.data)) {
          done = true
          scanner.stop()
        } else setStatus('notOurs')
      },
      { preferredCamera: 'environment', highlightScanRegion: true, highlightCodeOutline: true, maxScansPerSecond: 10 },
    )
    scanner.start().catch((err) => {
      const text = String(err?.name ?? err)
      setStatus(/NotAllowed|Permission/i.test(text) ? 'denied' : 'noCamera')
      setActive(false)
    })
    return () => scanner.destroy()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active])

  const startCamera = () => {
    if (!window.isSecureContext || !navigator.mediaDevices) return setStatus('insecure')
    setStatus('idle')
    setActive(true)
  }

  const scanPhoto = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setStatus('idle')
    try {
      const result = await QrScannerLib.scanImage(file, { returnDetailedScanResult: true })
      if (!open(result.data)) setStatus('notOurs')
    } catch {
      setStatus('noQr')
    }
  }

  const lookup = (e: FormEvent) => {
    e.preventDefault()
    if (!open(code)) setError(t('verify.badCode'))
  }

  const notice = {
    insecure: ['neutral', t('verify.cameraNeedsHttps')],
    noCamera: ['neutral', t('verify.noCamera')],
    denied: ['warning', t('verify.cameraDenied')],
    noQr: ['warning', t('verify.noQrInPhoto')],
    notOurs: ['warning', t('verify.badCode')],
  } as const

  return (
    <div className="space-y-4">
      {active ? (
        <div className="relative overflow-hidden rounded-md bg-forest-950">
          <video ref={videoRef} className="aspect-square w-full object-cover sm:aspect-video" muted playsInline />
          <Button variant="secondary" size="sm" icon={CameraOff} className="absolute right-3 bottom-3 z-10" onClick={() => setActive(false)}>
            {t('verify.stopCamera')}
          </Button>
        </div>
      ) : (
        <div className="grid gap-2 sm:grid-cols-2">
          <Button icon={Camera} size="lg" onClick={startCamera}>
            {t('verify.scanQr')}
          </Button>
          <Button icon={ImageUp} size="lg" variant="secondary" onClick={() => photoRef.current?.click()}>
            {t('verify.scanPhoto')}
          </Button>
        </div>
      )}
      <input ref={photoRef} type="file" accept="image/*" capture="environment" className="hidden" onChange={scanPhoto} />
      {status !== 'idle' && <Notice tone={notice[status][0]}>{notice[status][1]}</Notice>}
      <form onSubmit={lookup} className="flex gap-2">
        <label className="relative min-w-0 flex-1">
          <span className="sr-only">{t('verify.enterCode')}</span>
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted" aria-hidden />
          <input className="input num pl-9 font-mono uppercase" value={code} onChange={(e) => (setCode(e.target.value), setError(null))} placeholder="BATCH-7F3A" aria-invalid={Boolean(error)} />
        </label>
        <Button type="submit" variant="secondary">
          {t('verify.check')}
        </Button>
      </form>
      {error && <p className="text-xs text-danger-700">{error}</p>}
    </div>
  )
}
