import { Languages } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { LANGUAGES, type Lang } from '../i18n'
import { useAuth } from '../lib/auth'
import { cx } from './ui'

/** Kiswahili / English toggle. Signed-in users also get the choice saved to their
 * account, so SMS alerts and their next login use the same language. */
export function LanguageSwitcher({ tone = 'light', compact = false }: { tone?: 'light' | 'dark'; compact?: boolean }) {
  const { t, i18n } = useTranslation()
  const { setLanguage } = useAuth()
  const active = (i18n.resolvedLanguage ?? 'sw').startsWith('en') ? 'en' : 'sw'
  return (
    <div
      role="group"
      aria-label={t('language.label')}
      className={cx('inline-flex items-center rounded-md border p-0.5 text-xs font-semibold', tone === 'dark' ? 'border-white/25' : 'border-line-strong bg-surface')}
    >
      {!compact && <Languages className={cx('mx-1.5 size-3.5', tone === 'dark' ? 'text-white/70' : 'text-muted')} aria-hidden />}
      {LANGUAGES.map((lang) => {
        const selected = active === lang.code
        return (
          <button
            key={lang.code}
            type="button"
            lang={lang.code}
            aria-pressed={selected}
            title={lang.label}
            onClick={() => setLanguage(lang.code as Lang)}
            className={cx(
              'min-h-8 min-w-9 rounded px-2',
              selected ? (tone === 'dark' ? 'bg-white text-forest-900' : 'bg-forest-800 text-white') : tone === 'dark' ? 'text-white/85 hover:bg-white/10' : 'text-ink-soft hover:bg-sunken',
            )}
          >
            {compact ? lang.short : lang.label}
          </button>
        )
      })}
    </div>
  )
}
