import { AlertTriangle, Bell, Download, History, Radio } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Badge, Button, Card, EmptyState, ErrorState, Loading, PageHeader, Stat, StatStrip, cx } from '../../components/ui'
import { currentLang } from '../../i18n'
import { api, apiBlob } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { useBi, useErrorText, useFormat, type Bi } from '../../lib/hooks'

type Format = 'tzs' | 'kg' | 'count' | 'pct' | 'date' | 'acres' | 'text'
type Item = { label: Bi; value: number | string | Bi | null; format: Format }
type Section = { key: string; title: Bi; items: Item[]; table: { columns: Bi[]; formats: Format[]; rows: (number | string | null)[][] } | null }
type Change = { at: string; kind: string; severity: 'INFO' | 'WARNING' | 'CRITICAL'; text: Bi; count: number }
type Report = { role: string; title: Bi; subject: string; generated_at: string; stamp: string; sections: Section[]; changes: Change[]; change_days: number }

const REFRESH_MS = 20_000

/** The signed-in user's automatic report: rebuilt from live data, refreshed while open, with
 * everything that changed since they last looked, and a PDF of the same report. */
export function ReportsPage() {
  const { t } = useTranslation()
  const bi = useBi()
  const f = useFormat()
  const errorText = useErrorText()
  const { user } = useAuth()
  const [report, setReport] = useState<Report | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [justUpdated, setJustUpdated] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const seenKey = `shamba.report.seen.${user?.id}`
  // When the user last looked: entries newer than this are marked "New".
  const [lastSeen] = useState(() => {
    try {
      return localStorage.getItem(seenKey) ?? ''
    } catch {
      return ''
    }
  })
  const stamp = useRef<string | null>(null)

  const load = useCallback(async () => {
    try {
      const next = await api<Report>('/reports/me')
      if (stamp.current && stamp.current !== next.stamp) {
        setJustUpdated(true)
        window.setTimeout(() => setJustUpdated(false), 6000)
      }
      stamp.current = next.stamp
      setReport(next)
      setError(null)
    } catch (err) {
      setError(err)
    }
  }, [])

  // Rebuilt on open, then every 20 s while the page is visible (and at once when it comes back).
  useEffect(() => {
    load()
    const timer = window.setInterval(() => document.visibilityState === 'visible' && load(), REFRESH_MS)
    const onShow = () => document.visibilityState === 'visible' && load()
    document.addEventListener('visibilitychange', onShow)
    return () => {
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', onShow)
    }
  }, [load])

  // Remember what the user has now seen, for the next visit.
  useEffect(() => {
    const newest = report?.changes[0]?.at
    if (!newest) return
    try {
      localStorage.setItem(seenKey, newest)
    } catch {
      /* private mode: "New" badges just won't persist */
    }
  }, [report, seenKey])

  const download = async () => {
    setDownloading(true)
    try {
      const lang = currentLang()
      const blob = await apiBlob(`/reports/me.pdf?lang=${lang}`)
      const url = URL.createObjectURL(blob)
      const a = Object.assign(document.createElement('a'), { href: url, download: `agritrust-report-${new Date().toISOString().slice(0, 10)}.pdf` })
      a.click()
      window.setTimeout(() => URL.revokeObjectURL(url), 5000)
    } catch (err) {
      setError(err)
    } finally {
      setDownloading(false)
    }
  }

  const show = (value: Item['value'], format: Format) => {
    if (value === null || value === undefined) return '—'
    if (typeof value === 'object') return bi(value)
    switch (format) {
      case 'tzs':
        return f.tzs(Number(value))
      case 'kg':
        return f.kg(Number(value))
      case 'pct':
        return `${value}%`
      case 'date':
        return f.date(String(value))
      case 'acres':
        return `${f.num(Number(value), 1)} ${t('farm.acres')}`
      case 'count':
        return f.num(Number(value))
      default:
        return String(value)
    }
  }

  if (!report && !error) return <Loading rows={4} />
  if (!report) return <ErrorState text={errorText(error)} onRetry={load} />
  const fresh = report.changes.filter((c) => !lastSeen || c.at > lastSeen).length

  return (
    <div className="space-y-5">
      <PageHeader
        title={bi(report.title)}
        subtitle={`${report.subject} · ${t('reports.generated', { time: f.dateTime(report.generated_at) })}`}
        actions={
          <>
            <span className={cx('inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium', justUpdated ? 'bg-forest-100 text-forest-900' : 'text-muted')} role="status" aria-live="polite">
              <Radio className={cx('size-3.5', justUpdated ? 'text-forest-700' : 'animate-pulse text-forest-700')} aria-hidden />
              {justUpdated ? t('reports.justUpdated') : t('reports.live')}
            </span>
            <Button icon={Download} busy={downloading} onClick={download}>
              {t('reports.pdf')}
            </Button>
          </>
        }
      />

      {report.sections.map((s) => (
        <Card key={s.key} title={bi(s.title)}>
          <StatStrip cols={s.items.length >= 6 ? 3 : s.items.length === 4 ? 4 : s.items.length <= 2 ? 2 : 3}>
            {s.items.map((i) => (
              <Stat key={i.label.en} label={bi(i.label)} value={show(i.value, i.format)} />
            ))}
          </StatStrip>
          {s.table && s.table.rows.length > 0 && (
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-line text-xs text-muted">
                    {s.table.columns.map((c, i) => (
                      <th key={i} className="py-2 pr-4 font-medium">
                        {bi(c)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {s.table.rows.map((row, r) => (
                    <tr key={r}>
                      {row.map((v, c) => (
                        <td key={c} className="num py-2 pr-4 whitespace-nowrap">
                          {show(v, s.table!.formats[c])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      ))}

      <Card
        title={
          <span className="inline-flex items-center gap-2">
            <History className="size-4" aria-hidden /> {t('reports.changes', { days: report.change_days })}
          </span>
        }
        actions={fresh > 0 ? <Badge tone="gold">{t('reports.newCount', { count: fresh })}</Badge> : undefined}
      >
        {!report.changes.length ? (
          <EmptyState compact icon={Bell} title={t('reports.noChanges')} />
        ) : (
          <ol className="-my-2 divide-y divide-line">
            {report.changes.map((c, i) => {
              const isNew = !lastSeen || c.at > lastSeen
              return (
                <li key={`${c.at}-${i}`} className="flex gap-3 py-2.5 text-sm">
                  <span className="num w-24 shrink-0 text-xs text-muted sm:w-32">{f.dateTime(c.at)}</span>
                  <span className="min-w-0 flex-1">
                    {c.severity !== 'INFO' && <AlertTriangle className={cx('mr-1 inline size-4 align-[-3px]', c.severity === 'CRITICAL' ? 'text-danger-700' : 'text-warn-700')} aria-hidden />}
                    {bi(c.text)}
                    {c.count > 1 && <span className="ml-1 text-xs text-muted">×{c.count}</span>}
                  </span>
                  {isNew && lastSeen && <Badge tone="gold">{t('reports.new')}</Badge>}
                </li>
              )
            })}
          </ol>
        )}
      </Card>
      <p className="text-xs text-muted">{t('reports.note')}</p>
    </div>
  )
}
