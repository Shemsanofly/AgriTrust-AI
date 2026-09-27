import { Camera, ImageOff, Trash2 } from 'lucide-react'
import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Button, Dialog, ErrorNote, Field, useToast } from '../../components/ui'
import { api, apiBlob } from '../../lib/api'
import { useErrorText, useFormat } from '../../lib/hooks'
import type { Farm } from './shared'

export type CropPhoto = { id: number; url: string; caption: string; created_at: string }

const CROPS = ['maize', 'beans', 'rice', 'sorghum', 'sunflower'] as const
const MAX_SIDE = 1600

/** Shrinks a phone photo (often 3-8 MB) to a JPEG of at most 1600 px, so it uploads quickly
 * on a slow connection. Falls back to the original file if the browser can't decode it. */
export async function shrink(file: File): Promise<Blob> {
  try {
    const bitmap = await createImageBitmap(file)
    const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height))
    const canvas = document.createElement('canvas')
    canvas.width = Math.round(bitmap.width * scale)
    canvas.height = Math.round(bitmap.height * scale)
    canvas.getContext('2d')!.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.82))
    return blob && blob.size < file.size ? blob : file
  } catch {
    return file
  }
}

/** A private image: fetched with the session token, shown from a local object URL. */
export function AuthImage({ src, alt, className }: { src: string; alt: string; className?: string }) {
  const [url, setUrl] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    let objectUrl: string | null = null
    let alive = true
    apiBlob(src)
      .then((blob) => {
        if (!alive) return
        objectUrl = URL.createObjectURL(blob)
        setUrl(objectUrl)
      })
      .catch(() => alive && setFailed(true))
    return () => {
      alive = false
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [src])
  if (failed)
    return (
      <span className={`flex items-center justify-center bg-sunken text-muted ${className ?? ''}`}>
        <ImageOff className="size-5" aria-label={alt} />
      </span>
    )
  return url ? <img src={url} alt={alt} className={`object-cover ${className ?? ''}`} /> : <span className={`animate-pulse bg-sunken ${className ?? ''}`} aria-hidden />
}

/** Photo strip under a crop: take or pick a photo, open one to view or delete it. */
export function CropPhotos({ cropId, cropName, photos, onChanged }: { cropId: number; cropName: string; photos: CropPhoto[]; onChanged: () => void }) {
  const { t } = useTranslation()
  const f = useFormat()
  const toast = useToast()
  const errorText = useErrorText()
  const input = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [open, setOpen] = useState<CropPhoto | null>(null)

  const upload = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setBusy(true)
    setError(null)
    try {
      const form = new FormData()
      form.append('file', await shrink(file), 'crop.jpg')
      await api(`/crops/${cropId}/photos`, { method: 'POST', body: form })
      toast(t('photos.added'))
      onChanged()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  const remove = async (photo: CropPhoto) => {
    try {
      await api(photo.url, { method: 'DELETE' })
      setOpen(null)
      toast(t('photos.deleted'))
      onChanged()
    } catch (err) {
      setError(errorText(err))
    }
  }

  return (
    <div className="mt-3">
      <div className="flex gap-2 overflow-x-auto pb-1">
        <button
          type="button"
          onClick={() => input.current?.click()}
          disabled={busy}
          className="flex size-16 shrink-0 flex-col items-center justify-center gap-0.5 rounded-md border border-dashed border-line-strong text-[11px] text-forest-800 hover:bg-forest-50 disabled:opacity-60"
        >
          <Camera className={`size-5 ${busy ? 'animate-pulse' : ''}`} aria-hidden />
          {busy ? t('photos.uploading') : t('photos.add')}
        </button>
        {photos.map((p) => (
          <button key={p.id} type="button" onClick={() => setOpen(p)} className="shrink-0 overflow-hidden rounded-md ring-1 ring-line" aria-label={t('photos.open', { crop: cropName, date: f.date(p.created_at) })}>
            <AuthImage src={p.url} alt={p.caption || cropName} className="block size-16" />
          </button>
        ))}
      </div>
      <input ref={input} type="file" accept="image/*" capture="environment" className="hidden" onChange={upload} />
      <ErrorNote text={error} />
      <Dialog
        open={open != null}
        onClose={() => setOpen(null)}
        title={cropName}
        wide
        footer={
          open && (
            <Button variant="danger" size="sm" icon={Trash2} onClick={() => remove(open)}>
              {t('photos.delete')}
            </Button>
          )
        }
      >
        {open && (
          <figure>
            <AuthImage src={open.url} alt={open.caption || cropName} className="max-h-[65vh] w-full rounded-md object-contain" />
            <figcaption className="mt-2 text-sm text-muted">
              {open.caption && <span className="text-ink">{open.caption} · </span>}
              {f.dateTime(open.created_at)}
            </figcaption>
          </figure>
        )}
      </Dialog>
    </div>
  )
}

/** Add another crop to an existing farm (farms can grow several crops, even intercropped). */
export function AddCropDialog({ farm, open, onClose, onDone }: { farm: Farm; open: boolean; onClose: () => void; onDone: () => void }) {
  const { t } = useTranslation()
  const toast = useToast()
  const errorText = useErrorText()
  const today = new Date().toISOString().slice(0, 10)
  const blank = { crop_type: 'beans', variety: '', acreage: '', planting_date: today, expected_harvest_date: '' }
  const [form, setForm] = useState(blank)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value })
  const acres = form.acreage.trim() ? Number(form.acreage.replace(',', '.')) : null

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (acres !== null && !(acres > 0 && acres <= farm.acreage)) return setError(t('crop.acreageMax', { acres: farm.acreage }))
    if (form.expected_harvest_date && form.expected_harvest_date <= form.planting_date) return setError(t('errors.harvest_before_planting'))
    setBusy(true)
    setError(null)
    try {
      await api(`/farms/${farm.id}/crops`, {
        method: 'POST',
        body: {
          crop_type: form.crop_type,
          variety: form.variety.trim() || null,
          acreage: acres,
          planting_date: form.planting_date,
          expected_harvest_date: form.expected_harvest_date || null,
          growth_stage: 'initial',
        },
      })
      toast(t('crop.added', { crop: t(`crops.${form.crop_type}`) }))
      setForm(blank)
      onDone()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={t('crop.addTitle', { farm: farm.name })}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" form="add-crop" busy={busy}>
            {t('common.save')}
          </Button>
        </>
      }
    >
      <form id="add-crop" onSubmit={submit} className="grid gap-4 sm:grid-cols-2" noValidate>
        <Field label={t('farm.crop')}>
          <select className="input" value={form.crop_type} onChange={set('crop_type')}>
            {CROPS.map((c) => (
              <option key={c} value={c}>
                {t(`crops.${c}`)}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t('crop.variety')} optional>
          <input className="input" value={form.variety} onChange={set('variety')} maxLength={60} placeholder="SC 403" />
        </Field>
        <Field label={`${t('farm.acreage')} (${t('farm.acres')})`} optional hint={t('crop.acreageHint', { acres: farm.acreage })}>
          <input className="input num" inputMode="decimal" value={form.acreage} onChange={set('acreage')} />
        </Field>
        <Field label={t('farm.planted')}>
          <input className="input" type="date" value={form.planting_date} onChange={set('planting_date')} />
        </Field>
        <Field label={t('farm.expectedHarvest')} optional>
          <input className="input" type="date" min={form.planting_date} value={form.expected_harvest_date} onChange={set('expected_harvest_date')} />
        </Field>
        <div className="sm:col-span-2">
          <ErrorNote text={error} />
        </div>
      </form>
    </Dialog>
  )
}
