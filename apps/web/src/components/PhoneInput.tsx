import { useState } from 'react'
import { useTranslation } from 'react-i18next'

/** Country calling codes: East Africa first, then other common ones. */
export const COUNTRIES = [
  ['TZ', '255'],
  ['KE', '254'],
  ['UG', '256'],
  ['RW', '250'],
  ['BI', '257'],
  ['CD', '243'],
  ['MZ', '258'],
  ['MW', '265'],
  ['ZM', '260'],
  ['ET', '251'],
  ['SS', '211'],
  ['SO', '252'],
  ['NG', '234'],
  ['GH', '233'],
  ['ZA', '27'],
  ['IN', '91'],
  ['GB', '44'],
  ['US', '1'],
] as const
type Country = (typeof COUNTRIES)[number][0]

/** Splits "+255712345678" into its country and local number (longest matching code wins). */
function split(full: string): { country: Country | null; local: string } {
  const digits = full.replace(/\D/g, '')
  if (!full.trim().startsWith('+')) return { country: null, local: digits }
  const match = [...COUNTRIES].sort((a, b) => b[1].length - a[1].length).find(([, code]) => digits.startsWith(code))
  return match ? { country: match[0], local: digits.slice(match[1].length) } : { country: null, local: digits }
}

/** Phone field with a country-code picker. `value` and `onChange` use the full
 * international number (+255712345678); a leading 0 on the local number is dropped. */
export function PhoneInput({
  value,
  onChange,
  invalid,
  label,
  id,
  defaultCountry = 'TZ',
}: {
  value: string
  onChange: (full: string) => void
  invalid?: boolean
  /** Accessible name of the number box (the surrounding <label> names the first control). */
  label: string
  id?: string
  defaultCountry?: Country
}) {
  const { t } = useTranslation()
  const parsed = split(value)
  // Remember the picked country even while the number is empty.
  const [picked, setPicked] = useState<Country>(parsed.country ?? defaultCountry)
  const country = parsed.country ?? picked
  const code = COUNTRIES.find(([c]) => c === country)![1]
  const emit = (c: Country, local: string) => {
    const digits = local.replace(/\D/g, '').replace(/^0+/, '')
    onChange(digits ? `+${COUNTRIES.find(([x]) => x === c)![1]}${digits}` : '')
  }

  return (
    <div className="flex gap-2">
      <select
        className="input w-auto shrink-0 pr-7"
        value={country}
        aria-label={t('auth.countryCode')}
        onChange={(e) => {
          const next = e.target.value as Country
          setPicked(next)
          emit(next, parsed.local)
        }}
      >
        {COUNTRIES.map(([c, dial]) => (
          <option key={c} value={c}>
            {c} +{dial}
          </option>
        ))}
      </select>
      <input
        id={id}
        className="input num min-w-0 flex-1"
        type="tel"
        inputMode="tel"
        autoComplete="tel-national"
        placeholder={code === '255' ? '712 345 678' : ''}
        value={parsed.local}
        aria-label={label}
        aria-invalid={invalid || undefined}
        onChange={(e) => {
          // Pasting a full "+254…" number switches the country too.
          if (e.target.value.trim().startsWith('+')) {
            const again = split(e.target.value)
            if (again.country) setPicked(again.country)
            return onChange(e.target.value.replace(/[^\d+]/g, ''))
          }
          emit(country, e.target.value)
        }}
        required
      />
    </div>
  )
}
