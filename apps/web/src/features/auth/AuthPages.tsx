import { ArrowRight, Fingerprint, Lock, ScanFace, ShieldCheck } from 'lucide-react'
import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
import { BrandMark } from '../../components/Layout'
import { LanguageSwitcher } from '../../components/LanguageSwitcher'
import { PhoneInput } from '../../components/PhoneInput'
import { Button, ErrorNote, Field, Notice, Segmented } from '../../components/ui'
import { currentLang } from '../../i18n'
import { ApiError, api, setTokens } from '../../lib/api'
import { rememberedPhone, useAuth } from '../../lib/auth'
import { biometricAvailable } from '../../lib/biometric'
import { enrollFace, faceConfig, faceErrorKey, recogniseFace } from '../../lib/faceio'
import { useErrorText } from '../../lib/hooks'

const DEMO = [
  ['+255700000001', 'FARMER', 'Mama Neema'],
  ['+255700000002', 'BUYER', 'Tanzanite Foods'],
  ['+255700000003', 'WAREHOUSE_OPERATOR', 'Ghala la Chamwino'],
  ['+255700000004', 'LENDER', 'Kilimo Microfinance'],
  ['+255700000005', 'INSURER', 'Shamba Insurance'],
  ['+255700000009', 'ADMIN', 'Admin'],
] as const

function AuthShell({ children, title, subtitle }: { children: ReactNode; title: string; subtitle?: string }) {
  const { t } = useTranslation()
  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[1.1fr_1fr]">
      <aside className="relative hidden overflow-hidden bg-forest-900 lg:block">
        <img src="/images/farm-dodoma.jpg" alt="" className="absolute inset-0 size-full object-cover opacity-45" />
        <div className="relative flex h-full flex-col justify-between p-10 text-white">
          <div className="flex items-center gap-3">
            <BrandMark className="size-9" />
            <span className="text-lg font-semibold">{t('app.name')}</span>
          </div>
          <div className="max-w-md">
            <p className="text-3xl leading-tight font-semibold">{t('app.tagline')}</p>
            <ol className="mt-6 grid grid-cols-4 gap-2 text-sm">
              {(['shambani', 'ghalani', 'sokoni', 'kifedha'] as const).map((stage, i) => (
                <li key={stage} className="border-t-2 border-harvest-500/80 pt-2">
                  <div className="text-xs text-white/60">0{i + 1}</div>
                  <div className="font-semibold">{t(`journey.${stage}`)}</div>
                </li>
              ))}
            </ol>
          </div>
          <p className="text-xs text-white/60">{t('auth.photoCredit')}</p>
        </div>
      </aside>
      <div className="flex min-h-dvh flex-col px-5 py-5 sm:px-10">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 lg:invisible">
            <BrandMark className="size-8" />
            <span className="font-semibold">{t('app.name')}</span>
          </div>
          <div className="sm:hidden">
            <LanguageSwitcher compact />
          </div>
          <div className="hidden sm:block">
            <LanguageSwitcher />
          </div>
        </div>
        <div className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center py-10">
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
          <div className="mt-7">{children}</div>
        </div>
      </div>
    </div>
  )
}

export function LoginPage() {
  const { t } = useTranslation()
  const { login, loginWithBiometric, completeLogin } = useAuth()
  const errorText = useErrorText()
  const navigate = useNavigate()
  const [phone, setPhone] = useState(rememberedPhone())
  const [pin, setPin] = useState('')
  const [busy, setBusy] = useState<'pin' | 'bio' | 'face' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [bio, setBio] = useState(false)
  const [face, setFace] = useState(false)
  const [pinWrong, setPinWrong] = useState(false)

  useEffect(() => {
    biometricAvailable().then(setBio)
    faceConfig().then((c) => setFace(c.enabled))
  }, [])

  const describe = (err: unknown) => {
    if (err instanceof ApiError && err.code === 'invalid_credentials' && typeof err.details.attempts_left === 'number') {
      return t('auth.attemptsLeft', { count: err.details.attempts_left })
    }
    if (err instanceof ApiError && err.code === 'no_passkey') return t('security.noPasskeyYet')
    if (err instanceof ApiError && err.code === 'face_not_recognised') return t('face.err.notLinked')
    if (!(err instanceof ApiError)) return t('security.biometricCancelled')
    return errorText(err)
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy('pin')
    setError(null)
    try {
      await login(phone.trim(), pin)
      navigate('/')
    } catch (err) {
      setError(describe(err))
      setPinWrong(true)
      setPin('')
    } finally {
      setBusy(null)
    }
  }

  const biometric = async () => {
    setBusy('bio')
    setError(null)
    try {
      await loginWithBiometric(phone.trim())
      navigate('/')
    } catch (err) {
      setError(describe(err))
    } finally {
      setBusy(null)
    }
  }

  const faceLogin = async () => {
    setBusy('face')
    setError(null)
    try {
      const facialId = await recogniseFace()
      completeLogin(await api('/auth/face/login', { method: 'POST', body: { facial_id: facialId }, auth: false }))
      navigate('/')
    } catch (err) {
      setError(err instanceof ApiError ? describe(err) : t(`face.err.${faceErrorKey(err)}`))
    } finally {
      setBusy(null)
    }
  }

  return (
    <AuthShell title={t('auth.loginTitle')} subtitle={t('auth.loginSubtitle')}>
      <form onSubmit={submit} className="space-y-4" noValidate>
        <Field label={t('auth.phone')}>
          <PhoneInput label={t('auth.phone')} value={phone} onChange={setPhone} />
        </Field>
        <Field label={t('auth.pin')}>
          <div className="relative">
            <Lock className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted" aria-hidden />
            <input
              className="input pl-9 tracking-[0.3em]"
              type="password"
              inputMode="numeric"
              autoComplete="current-password"
              maxLength={6}
              value={pin}
              aria-invalid={pinWrong}
              onChange={(e) => (setPin(e.target.value.replace(/\D/g, '')), setPinWrong(false))}
              required
            />
          </div>
        </Field>
        <ErrorNote text={error} />
        <Button type="submit" size="lg" busy={busy === 'pin'} disabled={!phone || pin.length < 4} className="w-full">
          {t('auth.login')}
        </Button>
        {bio && (
          <Button variant="secondary" size="lg" icon={Fingerprint} busy={busy === 'bio'} disabled={!phone} onClick={biometric} className="w-full">
            {t('auth.loginBiometric')}
          </Button>
        )}
        {face && (
          <Button variant="secondary" size="lg" icon={ScanFace} busy={busy === 'face'} onClick={faceLogin} className="w-full">
            {t('face.signIn')}
          </Button>
        )}
      </form>
      <p className="mt-6 text-sm text-muted">
        {t('auth.noAccount')}{' '}
        <Link to="/register" className="font-medium text-forest-800 underline underline-offset-2">
          {t('auth.register')}
        </Link>
      </p>
      <p className="mt-3 flex items-start gap-2 text-xs text-muted">
        <ShieldCheck className="mt-px size-4 shrink-0" aria-hidden />
        {t('auth.securityNote')}
      </p>
      <details className="mt-8 rounded-md border border-line bg-surface">
        <summary className="cursor-pointer px-4 py-3 text-sm font-medium">{t('auth.demoAccounts')}</summary>
        <div className="border-t border-line px-2 py-2">
          <p className="px-2 pb-2 text-xs text-muted">{t('auth.demoHint')}</p>
          {DEMO.map(([p, role, name]) => (
            <button
              key={p}
              type="button"
              onClick={() => {
                setPhone(p)
                setPin('1234')
              }}
              className="flex min-h-11 w-full items-center justify-between rounded px-2 text-left text-sm hover:bg-sunken"
            >
              <span className="font-medium">{name}</span>
              <span className="text-xs text-muted">{t(`roles.${role}`)}</span>
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
  const [form, setForm] = useState({ role: 'FARMER', full_name: '', phone: '', pin: '', pin2: '', region: '', district: '', cooperative: '', business_name: '', country: 'TZ' })
  const [otpStep, setOtpStep] = useState<{ devOtp?: string } | null>(null)
  // After OTP: the new account's sign-in, held until the optional Face ID step is done.
  const [faceStep, setFaceStep] = useState<Parameters<typeof completeLogin>[0] | null>(null)
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [touched, setTouched] = useState(false)
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value })

  const problems = {
    full_name: form.full_name.trim().length < 2 ? t('validation.name') : null,
    phone: !/^\+?[0-9]{9,15}$/.test(form.phone.replace(/\s/g, '')) ? t('validation.phone') : null,
    pin: !/^[0-9]{4,6}$/.test(form.pin) ? t('validation.pin') : null,
    pin2: form.pin2 !== form.pin ? t('validation.pinMatch') : null,
    region: form.role === 'FARMER' && !form.region.trim() ? t('validation.region') : null,
  }
  const show = (k: keyof typeof problems) => (touched ? problems[k] : null)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setTouched(true)
    if (Object.values(problems).some(Boolean)) return
    setBusy(true)
    setError(null)
    try {
      const body: Record<string, unknown> = {
        role: form.role,
        full_name: form.full_name.trim(),
        phone: form.phone.replace(/\s/g, ''),
        pin: form.pin,
        language: currentLang(), // the language in use now becomes the saved preference
      }
      if (form.role === 'FARMER') Object.assign(body, { region: form.region.trim(), district: form.district.trim(), cooperative: form.cooperative.trim() || null })
      else Object.assign(body, { business_name: form.business_name.trim() || form.full_name.trim(), country: form.country })
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
      const res = await api<Parameters<typeof completeLogin>[0]>('/auth/otp/verify', { method: 'POST', body: { phone: form.phone.replace(/\s/g, ''), code }, auth: false })
      if ((await faceConfig()).enabled) {
        // Tokens only: signing in fully would leave this page before the Face ID step.
        setTokens({ access_token: res.access_token, refresh_token: res.refresh_token })
        setFaceStep(res)
      } else {
        completeLogin(res)
        navigate('/')
      }
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  const finish = () => {
    completeLogin(faceStep!)
    navigate('/')
  }

  const addFace = async () => {
    setBusy(true)
    setError(null)
    try {
      const facialId = await enrollFace()
      await api('/auth/face/enroll', { method: 'POST', body: { facial_id: facialId } })
      finish()
    } catch (err) {
      setError(err instanceof ApiError ? errorText(err) : t(`face.err.${faceErrorKey(err)}`))
    } finally {
      setBusy(false)
    }
  }

  if (faceStep) {
    return (
      <AuthShell title={t('face.setupTitle')} subtitle={t('face.setupSubtitle')}>
        <div className="space-y-4">
          <div className="flex justify-center py-2">
            <span className="flex size-20 items-center justify-center rounded-full bg-forest-50 text-forest-800">
              <ScanFace className="size-10" aria-hidden />
            </span>
          </div>
          <ul className="space-y-2 text-sm text-ink-soft">
            {(['light', 'still', 'alone'] as const).map((tip) => (
              <li key={tip} className="flex gap-2">
                <span className="mt-2 size-1.5 shrink-0 rounded-full bg-forest-700" aria-hidden />
                {t(`face.tips.${tip}`)}
              </li>
            ))}
          </ul>
          <Notice tone="neutral">{t('face.privacy')}</Notice>
          <ErrorNote text={error} />
          <Button size="lg" icon={ScanFace} busy={busy} onClick={addFace} className="w-full">
            {t('face.setup')}
          </Button>
          <Button variant="ghost" size="lg" disabled={busy} onClick={finish} className="w-full">
            {t('face.skip')}
          </Button>
        </div>
      </AuthShell>
    )
  }

  if (otpStep) {
    return (
      <AuthShell title={t('auth.otpTitle')} subtitle={t('auth.otpSent', { phone: form.phone })}>
        <form onSubmit={verify} className="space-y-4">
          {otpStep.devOtp && <Notice tone="neutral">{t('auth.devOtp', { code: otpStep.devOtp })}</Notice>}
          <Field label={t('auth.otpCode')}>
            <input className="input text-center text-2xl tracking-[0.5em]" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))} />
          </Field>
          <ErrorNote text={error} />
          <Button type="submit" size="lg" busy={busy} disabled={code.length !== 6} className="w-full">
            {t('auth.verify')}
          </Button>
        </form>
      </AuthShell>
    )
  }

  return (
    <AuthShell title={t('auth.registerTitle')} subtitle={t('auth.registerSubtitle')}>
      <form onSubmit={submit} className="space-y-4" noValidate>
        <Segmented
          label={t('auth.iAm')}
          value={form.role}
          onChange={(role) => setForm({ ...form, role })}
          options={[
            { id: 'FARMER', label: t('roles.FARMER') },
            { id: 'BUYER', label: t('roles.BUYER') },
          ]}
        />
        <Field label={t('auth.fullName')} error={show('full_name')}>
          <input className="input" autoComplete="name" value={form.full_name} onChange={set('full_name')} aria-invalid={Boolean(show('full_name'))} />
        </Field>
        <Field label={t('auth.phone')} error={show('phone')}>
          <PhoneInput label={t('auth.phone')} value={form.phone} onChange={(phone) => setForm({ ...form, phone })} invalid={Boolean(show('phone'))} />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label={t('auth.choosePin')} error={show('pin')}>
            <input className="input tracking-[0.3em]" type="password" inputMode="numeric" autoComplete="new-password" maxLength={6} value={form.pin} onChange={set('pin')} aria-invalid={Boolean(show('pin'))} />
          </Field>
          <Field label={t('auth.repeatPin')} error={show('pin2')}>
            <input className="input tracking-[0.3em]" type="password" inputMode="numeric" autoComplete="new-password" maxLength={6} value={form.pin2} onChange={set('pin2')} aria-invalid={Boolean(show('pin2'))} />
          </Field>
        </div>
        {form.role === 'FARMER' ? (
          <>
            <div className="grid grid-cols-2 gap-3">
              <Field label={t('auth.region')} error={show('region')}>
                <input className="input" value={form.region} onChange={set('region')} placeholder="Dodoma" aria-invalid={Boolean(show('region'))} />
              </Field>
              <Field label={t('auth.district')} optional>
                <input className="input" value={form.district} onChange={set('district')} />
              </Field>
            </div>
            <Field label={t('auth.cooperative')} optional>
              <input className="input" value={form.cooperative} onChange={set('cooperative')} />
            </Field>
          </>
        ) : (
          <div className="grid grid-cols-[1fr_6rem] gap-3">
            <Field label={t('auth.businessName')}>
              <input className="input" value={form.business_name} onChange={set('business_name')} />
            </Field>
            <Field label={t('auth.country')}>
              <input className="input uppercase" value={form.country} onChange={set('country')} maxLength={2} />
            </Field>
          </div>
        )}
        <ErrorNote text={error} />
        <Button type="submit" size="lg" busy={busy} className="w-full">
          {t('auth.continue')} <ArrowRight className="size-4" aria-hidden />
        </Button>
        <p className="text-sm text-muted">
          <Link to="/login" className="font-medium text-forest-800 underline underline-offset-2">
            {t('auth.haveAccount')}
          </Link>
        </p>
      </form>
    </AuthShell>
  )
}
