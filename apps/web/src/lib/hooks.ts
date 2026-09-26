import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ApiError, api } from './api'

/** Bilingual text from the API ({en, sw}) in the language currently selected. */
export type Bi = { en: string; sw: string }

export function useBi() {
  const { i18n } = useTranslation()
  const lang = (i18n.resolvedLanguage ?? 'sw').startsWith('en') ? 'en' : 'sw'
  return useCallback((text?: Bi | null) => (text ? text[lang] ?? text.sw ?? text.en : ''), [lang])
}

export function useErrorText() {
  const { t } = useTranslation()
  return useCallback(
    (err: unknown) => {
      const code = err instanceof ApiError ? err.code : 'unknown'
      return t(`errors.${code}`, { defaultValue: t('errors.unknown') })
    },
    [t],
  )
}

export function useApi<T>(path: string | null, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [loading, setLoading] = useState(Boolean(path))
  const [tick, setTick] = useState(0)

  useEffect(() => {
    if (!path) return
    let cancelled = false
    setLoading(true)
    api<T>(path)
      .then((d) => !cancelled && (setData(d), setError(null)))
      .catch((e) => !cancelled && setError(e))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, tick, ...deps])

  const reload = useCallback(() => setTick((x) => x + 1), [])
  return { data, error, loading, reload, setData }
}

export function useFormat() {
  const { i18n } = useTranslation()
  const locale = (i18n.resolvedLanguage ?? 'sw').startsWith('en') ? 'en-TZ' : 'sw-TZ'
  return {
    num: (n: number | null | undefined, digits = 0) =>
      n == null ? '—' : new Intl.NumberFormat(locale, { maximumFractionDigits: digits }).format(n),
    tzs: (n: number | null | undefined) =>
      n == null ? '—' : `TZS ${new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }).format(n)}`,
    date: (s: string | null | undefined) => (s ? new Date(s).toLocaleDateString(locale, { day: 'numeric', month: 'short', year: 'numeric' }) : '—'),
    dateTime: (s: string | null | undefined) =>
      s ? new Date(s).toLocaleString(locale, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—',
    weekday: (s: string) => new Date(s).toLocaleDateString(locale, { weekday: 'short' }),
    time: (s: string) => new Date(s).toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' }),
  }
}
