import { useTranslation } from 'react-i18next'
import { LANGUAGES, type Lang } from '../i18n'
import { useAuth } from '../lib/auth'

/** Kiswahili / English toggle. Logged-in users also get the choice saved to their
 * account, so SMS alerts and their next login use the same language. */
export function LanguageSwitcher({ tone = 'light' }: { tone?: 'light' | 'dark' }) {
  const { t, i18n } = useTranslation()
  const { setLanguage } = useAuth()
  const active = (i18n.resolvedLanguage ?? 'sw').startsWith('en') ? 'en' : 'sw'
  const base = tone === 'dark' ? 'border-white/40' : 'border-stone-300 bg-white'
  return (
    <div role="group" aria-label={t('language.label')} className={`inline-flex overflow-hidden rounded-full border text-xs font-semibold ${base}`}>
      {LANGUAGES.map((lang) => {
        const selected = active === lang.code
        const style = selected
          ? tone === 'dark'
            ? 'bg-white text-brand-900'
            : 'bg-brand-800 text-white'
          : tone === 'dark'
            ? 'text-white hover:bg-white/10'
            : 'text-stone-700 hover:bg-stone-100'
        return (
          <button
            key={lang.code}
            type="button"
            lang={lang.code}
            aria-pressed={selected}
            title={lang.label}
            onClick={() => setLanguage(lang.code as Lang)}
            className={`px-3 py-1.5 ${style}`}
          >
            <span className="sm:hidden">{lang.short}</span>
            <span className="hidden sm:inline">{lang.label}</span>
          </button>
        )
      })}
    </div>
  )
}
