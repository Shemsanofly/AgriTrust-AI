import { Camera, CameraOff, Search } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { Button, Notice } from '../../components/ui'

/** Extracts a batch / receipt / sale id from a scanned QR (URL or bare id). */
export function idFromCode(raw: string): string | null {
  const m = raw.trim().match(/(BATCH-[A-Z0-9]+|WR-\d{4}-\d{6}|SALE-[A-Z0-9]+)/i)
  return m ? m[1].toUpperCase() : null
}

type Detector = { detect: (src: CanvasImageSource) => Promise<{ rawValue: string }[]> }

/** Camera QR scanning with the browser's built-in BarcodeDetector (no extra download on
 * a slow connection). Where it is not supported, typing the code always works. */
export function QrScanner() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const videoRef = useRef<HTMLVideoElement>(null)
  const [active, setActive] = useState(false)
  const [status, setStatus] = useState<'idle' | 'unsupported' | 'denied'>('idle')
  const [code, setCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const supported = typeof window !== 'undefined' && 'BarcodeDetector' in window

  useEffect(() => {
    if (!active) return
    let stream: MediaStream | null = null
    let raf = 0
    let stopped = false
    const Ctor = (window as any).BarcodeDetector
    const detector: Detector = new Ctor({ formats: ['qr_code'] })
    navigator.mediaDevices
      ?.getUserMedia({ video: { facingMode: 'environment' } })
      .then((s) => {
        stream = s
        if (!videoRef.current) return
        videoRef.current.srcObject = s
        videoRef.current.play()
        const tick = async () => {
          if (stopped || !videoRef.current) return
          try {
            const found = await detector.detect(videoRef.current)
            const id = found.map((f) => idFromCode(f.rawValue)).find(Boolean)
            if (id) {
              navigate(`/verify/${id}`)
              return
            }
          } catch {
            /* frame not ready */
          }
          raf = requestAnimationFrame(tick)
        }
        tick()
      })
      .catch(() => {
        setStatus('denied')
        setActive(false)
      })
    return () => {
      stopped = true
      cancelAnimationFrame(raf)
      stream?.getTracks().forEach((tr) => tr.stop())
    }
  }, [active, navigate])

  const lookup = (e: FormEvent) => {
    e.preventDefault()
    const id = idFromCode(code)
    if (!id) return setError(t('verify.badCode'))
    navigate(`/verify/${id}`)
  }

  return (
    <div className="space-y-4">
      {active ? (
        <div className="relative overflow-hidden rounded-md bg-forest-950">
          <video ref={videoRef} className="aspect-square w-full object-cover sm:aspect-video" muted playsInline />
          <div className="pointer-events-none absolute inset-[18%] rounded-lg border-2 border-white/80" aria-hidden />
          <Button variant="secondary" size="sm" icon={CameraOff} className="absolute right-3 bottom-3" onClick={() => setActive(false)}>
            {t('verify.stopCamera')}
          </Button>
        </div>
      ) : (
        <Button
          icon={Camera}
          size="lg"
          className="w-full"
          onClick={() => (supported ? (setStatus('idle'), setActive(true)) : setStatus('unsupported'))}
        >
          {t('verify.scanQr')}
        </Button>
      )}
      {status === 'unsupported' && <Notice tone="neutral">{t('verify.scanUnsupported')}</Notice>}
      {status === 'denied' && <Notice tone="warning">{t('verify.cameraDenied')}</Notice>}
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
