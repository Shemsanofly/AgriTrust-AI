import { Download, FileText, Image as ImageIcon, Paperclip, Trash2, Upload } from 'lucide-react'
import { useEffect, useRef, useState, type ChangeEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Button, Dialog, ErrorNote } from '../../components/ui'
import { api, apiBlob } from '../../lib/api'
import { useErrorText } from '../../lib/hooks'
import { shrink } from '../farmer/CropExtras'

export type LoanDoc = { id: number; doc_type: string; name: string; content_type: string; size_bytes: number; url: string; attached: boolean; created_at: string }

const TYPES = ['national_id', 'land', 'cooperative', 'other'] as const
const kb = (n: number) => (n >= 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`)

/** Opens a private document (sent with the session token): photos inline, PDFs in a viewer
 * with a download link (phones often can't show a PDF inside a page). */
function DocumentViewer({ doc, onClose }: { doc: LoanDoc | null; onClose: () => void }) {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const [url, setUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    if (!doc) return
    let objectUrl: string | null = null
    setUrl(null)
    setError(null)
    apiBlob(doc.url)
      .then((blob) => setUrl((objectUrl = URL.createObjectURL(blob))))
      .catch((err) => setError(errorText(err)))
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [doc, errorText])
  return (
    <Dialog
      open={doc != null}
      onClose={onClose}
      wide
      title={doc ? `${t(`loanDocs.types.${doc.doc_type}`)} · ${doc.name}` : ''}
      footer={
        url && doc ? (
          <a href={url} download={doc.name} className="inline-flex min-h-9 items-center gap-1.5 rounded-md border border-line-strong px-3 text-[13px] font-medium hover:bg-sunken">
            <Download className="size-4" aria-hidden /> {t('loanDocs.download')}
          </a>
        ) : undefined
      }
    >
      <ErrorNote text={error} />
      {!url && !error && <div className="h-64 animate-pulse rounded-md bg-sunken" />}
      {url && doc?.content_type === 'application/pdf' && <iframe src={url} title={doc.name} className="h-[65vh] w-full rounded-md border border-line" />}
      {url && doc && doc.content_type !== 'application/pdf' && <img src={url} alt={doc.name} className="max-h-[65vh] w-full rounded-md object-contain" />}
    </Dialog>
  )
}

/** Read-only list (farmer's past applications, lender's review). */
export function DocumentList({ docs }: { docs: LoanDoc[] }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState<LoanDoc | null>(null)
  return (
    <>
      <ul className="space-y-1.5">
        {docs.map((d) => {
          const Icon = d.content_type === 'application/pdf' ? FileText : ImageIcon
          return (
            <li key={d.id}>
              <button type="button" onClick={() => setOpen(d)} className="flex w-full items-center gap-2.5 rounded-md border border-line px-3 py-2 text-left text-[13px] hover:bg-sunken">
                <Icon className="size-4 shrink-0 text-forest-800" aria-hidden />
                <span className="min-w-0 flex-1">
                  <span className="font-medium">{t(`loanDocs.types.${d.doc_type}`)}</span>
                  <span className="block truncate text-xs text-muted">
                    {d.name} · {kb(d.size_bytes)}
                  </span>
                </span>
                <span className="text-xs font-medium text-forest-800">{t('loanDocs.open')}</span>
              </button>
            </li>
          )
        })}
      </ul>
      <DocumentViewer doc={open} onClose={() => setOpen(null)} />
    </>
  )
}

/** Upload step of the loan application: pick the kind of document, then a PDF or photo. */
export function DocumentPicker({ docs, onChange, error: fieldError }: { docs: LoanDoc[]; onChange: (docs: LoanDoc[]) => void; error?: string | null }) {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const input = useRef<HTMLInputElement>(null)
  const [docType, setDocType] = useState<(typeof TYPES)[number]>('national_id')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [open, setOpen] = useState<LoanDoc | null>(null)

  // Documents uploaded earlier but not sent with an application yet.
  useEffect(() => {
    api<LoanDoc[]>('/loan-documents').then(onChange).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const upload = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setBusy(true)
    setError(null)
    try {
      const form = new FormData()
      const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
      form.append('file', isPdf ? file : await shrink(file), isPdf ? file.name : file.name.replace(/\.\w+$/, '') + '.jpg')
      form.append('doc_type', docType)
      const doc = await api<LoanDoc>('/loan-documents', { method: 'POST', body: form })
      onChange([...docs, doc])
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  const remove = async (doc: LoanDoc) => {
    try {
      await api(doc.url, { method: 'DELETE' })
      onChange(docs.filter((d) => d.id !== doc.id))
    } catch (err) {
      setError(errorText(err))
    }
  }

  return (
    <div role="group" aria-labelledby="loan-docs-title">
      <div id="loan-docs-title" className="label">{t('loanDocs.title')}</div>
      <div className="space-y-2">
        <div className="flex gap-2">
          <select className="input min-w-0 flex-1" value={docType} onChange={(e) => setDocType(e.target.value as (typeof TYPES)[number])} aria-label={t('loanDocs.type')}>
            {TYPES.map((x) => (
              <option key={x} value={x}>
                {t(`loanDocs.types.${x}`)}
              </option>
            ))}
          </select>
          <Button variant="secondary" icon={Upload} busy={busy} onClick={() => input.current?.click()} className="shrink-0">
            {t('loanDocs.upload')}
          </Button>
        </div>
        <input ref={input} type="file" accept="application/pdf,image/*" className="hidden" onChange={upload} />
        {docs.map((d) => (
          <div key={d.id} className="flex items-center gap-2 rounded-md bg-sunken px-3 py-2 text-[13px]">
            <Paperclip className="size-4 shrink-0 text-forest-800" aria-hidden />
            <button type="button" onClick={() => setOpen(d)} className="min-w-0 flex-1 truncate text-left">
              <span className="font-medium">{t(`loanDocs.types.${d.doc_type}`)}</span> <span className="text-muted">· {d.name}</span>
            </button>
            <button type="button" onClick={() => remove(d)} className="flex size-8 items-center justify-center rounded-md text-muted hover:bg-surface hover:text-danger-700" aria-label={t('loanDocs.remove', { name: d.name })}>
              <Trash2 className="size-4" aria-hidden />
            </button>
          </div>
        ))}
        <ErrorNote text={error} />
      </div>
      {fieldError ? <p className="mt-1 text-xs text-danger-700">{fieldError}</p> : <p className="mt-1 text-xs text-muted">{t('loanDocs.hint')}</p>}
      <DocumentViewer doc={open} onClose={() => setOpen(null)} />
    </div>
  )
}
