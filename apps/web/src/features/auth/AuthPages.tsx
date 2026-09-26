import { useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
import { LanguageSwitcher } from '../../components/LanguageSwitcher'
import { Button, ErrorNote, Field } from '../../components/ui'
import { currentLang } from '../../i18n'
import { api } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { useErrorText } from '../../lib/hooks'

const DEMO = [
  ['+255700000001', 'FARMER', 'Mama Neema'],
  ['+255700000002', 'BUYER', 'Tanzanite Foods'],
  ['+255700000003', 'WAREHOUSE_OPERATOR', 'Ghala la Chamwino'],
  ['+255700000004', 'LENDER', 'Kilimo Microfinance'],
  ['+255700000005', 'INSURER', 'Shamba Insurance'],
  ['+255700000009', 'ADMIN', 'Admin'],
] as const

function AuthShell({ children }: { children: ReactNode }) {
  const { t } = useTranslation()
  return (
    <div className="min-h-screen bg-gradient-to-b from-brand-900 to-brand-700 px-4 py-6">
      <div className="mx-auto flex max-w-md items-center justify-between text-white">
        <span className="text-sm font-semibold">🌱 {t('app.name')}</span>
        <LanguageSwitcher tone="dark" />
      </div>
      <div className="mx-auto mt-8 max-w-md">
        <h1 className="text-center text-2xl font-bold text-white">{t('app.tagline')}</h1>
        <p className="mt-1 text-center text-sm text-white/80">{t('app.stages')}</p>
        <div className="mt-6 rounded-2xl bg-white p-5 shadow-xl">{children}</div>
      </div>
    </div>
  )
}

export function LoginPage() {
  const { t } = useTranslation()
  const { login } = useAuth()
  const errorText = useErrorText()
  const navigate = useNavigate()
  const [phone, setPhone] = useState('')
  const [pin, setPin] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(phone.trim(), pin)
      navigate('/')
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell>
      <form onSubmit={submit} className="space-y-4">
        <h2 className="text-lg font-semibold">{t('auth.loginTitle')}</h2>
        <Field label={t('auth.phone')}>
          <input className="input" type="tel" inputMode="tel" autoComplete="tel" placeholder="+2557…" value={phone} onChange={(e) => setPhone(e.target.value)} required />
        </Field>
        <Field label={t('auth.pin')}>
          <input
            className="input tracking-widest"
            type="password"
            inputMode="numeric"
            autoComplete="current-password"
            maxLength={6}
            value={pin}
            onChange={(e) => setPin(e.target.value.replace(/\D/g, ''))}
            required
          />
        </Field>
        <ErrorNote text={error} />
        <Button type="submit" busy={busy} className="w-full">
          {t('auth.login')}
        </Button>
        <p className="text-center text-sm text-stone-600">
          {t('auth.noAccount')}{' '}
          <Link to="/register" className="font-semibold text-brand-800 underline">
            {t('auth.register')}
          </Link>
        </p>
        <p className="text-center text-xs text-stone-500">{t('auth.biometricsSoon')}</p>
      </form>
      <details className="mt-5 rounded-xl bg-stone-50 p-3 text-sm">
        <summary className="cursor-pointer font-medium text-stone-700">{t('auth.demoAccounts')}</summary>
        <p className="mt-2 text-xs text-stone-500">{t('auth.demoHint')}</p>
        <div className="mt-2 grid gap-1">
          {DEMO.map(([p, role, name]) => (
            <button
              key={p}
              type="button"
              onClick={() => {
                setPhone(p)
                setPin('1234')
              }}
              className="flex justify-between rounded-lg px-2 py-1.5 text-left hover:bg-white"
            >
              <span>{name}</span>
              <span className="text-xs text-stone-500">{t(`roles.${role}`)}</span>
            </button>
          ))}
        </div>
      </details>
    </AuthShell>
  )
}

export function RegisterPage() {
  const { t } = useTranslation()
  const { completeLogin } = useAuth()
  const errorText = useErrorText()
  const navigate = useNavigate()
  const [form, setForm] = useState({
    role: 'FARMER',
    full_name: '',
    phone: '',
    pin: '',
    region: '',
    district: '',
    cooperative: '',
    business_name: '',
    country: 'TZ',
  })
  const [otpStep, setOtpStep] = useState<{ devOtp?: string } | null>(null)
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value })

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const body: Record<string, unknown> = {
        role: form.role,
        full_name: form.full_name,
        phone: form.phone.trim(),
        pin: form.pin,
        // Save the language the person is using right now as their preference.
        language: currentLang(),
      }
      if (form.role === 'FARMER') Object.assign(body, { region: form.region, district: form.district, cooperative: form.cooperative || null })
      else Object.assign(body, { business_name: form.business_name || form.full_name, country: form.country })
      const res = await api('/auth/register', { method: 'POST', body, auth: false })
      setOtpStep({ devOtp: res.dev_otp })
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  const verify = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      completeLogin(await api('/auth/otp/verify', { method: 'POST', body: { phone: form.phone.trim(), code }, auth: false }))
      navigate('/')
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  if (otpStep) {
    return (
      <AuthShell>
        <form onSubmit={verify} className="space-y-4">
          <h2 className="text-lg font-semibold">{t('auth.otpTitle')}</h2>
          <p className="text-sm text-stone-600">{t('auth.otpSent', { phone: form.phone })}</p>
          {otpStep.devOtp && <p className="rounded-lg bg-purple-50 px-3 py-2 text-sm text-purple-800">{t('auth.devOtp', { code: otpStep.devOtp })}</p>}
          <Field label={t('auth.otpCode')}>
            <input className="input text-center text-xl tracking-[0.4em]" inputMode="numeric" maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))} required />
          </Field>
          <ErrorNote text={error} />
          <Button type="submit" busy={busy} className="w-full">
            {t('auth.verify')}
          </Button>
        </form>
      </AuthShell>
    )
  }

  return (
    <AuthShell>
      <form onSubmit={submit} className="space-y-3">
        <h2 className="text-lg font-semibold">{t('auth.registerTitle')}</h2>
        <div className="grid grid-cols-2 gap-2">
          {(['FARMER', 'BUYER'] as const).map((role) => (
            <button
              type="button"
              key={role}
              onClick={() => setForm({ ...form, role })}
              className={`rounded-xl border p-3 text-sm font-medium ${form.role === role ? 'border-brand-700 bg-brand-50 text-brand-900' : 'border-stone-200'}`}
            >
              {role === 'FARMER' ? '🌱' : '🧺'} {t(`roles.${role}`)}
            </button>
          ))}
        </div>
        <Field label={t('auth.fullName')}>
          <input className="input" value={form.full_name} onChange={set('full_name')} required minLength={2} />
        </Field>
        <Field label={t('auth.phone')}>
          <input className="input" type="tel" placeholder="+2557…" value={form.phone} onChange={set('phone')} required pattern="\+?[0-9]{9,15}" />
        </Field>
        <Field label={t('auth.choosePin')} hint={t('auth.pinHint')}>
          <input className="input" type="password" inputMode="numeric" maxLength={6} pattern="[0-9]{4,6}" value={form.pin} onChange={set('pin')} required />
        </Field>
        {form.role === 'FARMER' ? (
          <>
            <div className="grid grid-cols-2 gap-2">
              <Field label={t('auth.region')}>
                <input className="input" value={form.region} onChange={set('region')} required placeholder="Dodoma" />
              </Field>
              <Field label={t('auth.district')}>
                <input className="input" value={form.district} onChange={set('district')} />
              </Field>
            </div>
            <Field label={t('auth.cooperative')}>
              <input className="input" value={form.cooperative} onChange={set('cooperative')} />
            </Field>
          </>
        ) : (
          <div className="grid grid-cols-2 gap-2">
            <Field label={t('auth.businessName')}>
              <input className="input" value={form.business_name} onChange={set('business_name')} />
            </Field>
            <Field label={t('auth.country')}>
              <input className="input" value={form.country} onChange={set('country')} maxLength={2} />
            </Field>
          </div>
        )}
        <p className="text-xs text-stone-500">{t('auth.languageSaved')}</p>
        <ErrorNote text={error} />
        <Button type="submit" busy={busy} className="w-full">
          {t('auth.register')}
        </Button>
        <p className="text-center text-sm">
          <Link to="/login" className="text-brand-800 underline">
            {t('auth.haveAccount')}
          </Link>
        </p>
      </form>
    </AuthShell>
  )
}
