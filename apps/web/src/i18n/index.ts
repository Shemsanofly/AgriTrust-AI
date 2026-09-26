import i18n from 'i18next'
import LanguageDetector from 'i18next-browser-languagedetector'
import { initReactI18next } from 'react-i18next'
import en from './en.json'
import sw from './sw.json'

export const LANGUAGES = [
  { code: 'sw', label: 'Kiswahili', short: 'SW' },
  { code: 'en', label: 'English', short: 'EN' },
] as const
export type Lang = (typeof LANGUAGES)[number]['code']
export const STORAGE_KEY = 'shamba.lang'

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: { sw: { translation: sw }, en: { translation: en } },
    supportedLngs: ['sw', 'en'],
    nonExplicitSupportedLngs: true,
    fallbackLng: 'sw', // Kiswahili first
    interpolation: { escapeValue: false },
    detection: {
      order: ['localStorage', 'navigator'],
      lookupLocalStorage: STORAGE_KEY,
      caches: ['localStorage'],
    },
  })

const syncHtmlLang = (lng: string) => {
  document.documentElement.lang = lng.startsWith('en') ? 'en' : 'sw'
}
syncHtmlLang(i18n.resolvedLanguage ?? 'sw')
i18n.on('languageChanged', syncHtmlLang)

export function currentLang(): Lang {
  return (i18n.resolvedLanguage ?? i18n.language ?? 'sw').startsWith('en') ? 'en' : 'sw'
}

export default i18n
