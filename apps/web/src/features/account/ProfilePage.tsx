import { Fingerprint, KeyRound, Laptop, LogOut, ShieldCheck, Smartphone, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { LanguageSwitcher } from '../../components/LanguageSwitcher'
import { Badge, Button, Card, EmptyState, ErrorNote, KeyValues, Notice, PageHeader, Skeleton, useToast } from '../../components/ui'
import { ApiError, api } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { biometricAvailable, enrolBiometric } from '../../lib/biometric'
import { useApi, useErrorText, useFormat } from '../../lib/hooks'

type Session = { id: number; device: string; login_method: string; started_at: string; last_active_at: string; current: boolean }
type Security = { passkeys: { id: number; label: string; created_at: string; last_used_at: string | null }[] }

export function ProfilePage() {
  const { t } = useTranslation()
  const f = useFormat()
  const toast = useToast()
  const errorText = useErrorText()
  const { user, logout, refreshSecurity } = useAuth()
  const { data: security, reload: reloadSecurity } = useApi<Security>('/me/security')
  const { data: sessions, loading: sessionsLoading, reload: reloadSessions } = useApi<Session[]>('/me/sessions')
  const [supported, setSupported] = useState<boolean | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    biometricAvailable().then(setSupported)
  }, [])
  if (!user) return null

  const enrol = async () => {
    setBusy('enrol')
    setError(null)
    try {
      await enrolBiometric(t('security.thisPhone'))
      reloadSecurity()
      refreshSecurity()
      toast(t('security.biometricOn'))
    } catch (err) {
      setError(err instanceof ApiError ? errorText(err) : t('security.biometricCancelled'))
    } finally {
      setBusy(null)
    }
  }

  const removeKey = async (id: number) => {
    await api(`/auth/webauthn/credentials/${id}`, { method: 'DELETE' })
    reloadSecurity()
    refreshSecurity()
  }

  const revoke = async (id: number) => {
    await api(`/me/sessions/${id}`, { method: 'DELETE' })
    reloadSessions()
  }

  const revokeOthers = async () => {
    setBusy('others')
    await api('/me/sessions/revoke-others', { method: 'POST' }).catch(() => {})
    setBusy(null)
    reloadSessions()
    toast(t('security.othersSignedOut'))
  }

  const identity: [string, string][] = [
    [t('auth.fullName'), user.full_name],
    [t('auth.phone'), user.phone],
    [t('profile.role'), t(`roles.${user.role}`)],
  ]
  if (user.farmer) identity.push([t('profile.farmerId'), user.farmer.public_id], [t('auth.region'), [user.farmer.region, user.farmer.district].filter(Boolean).join(', ')])
  if (user.farmer?.cooperative) identity.push([t('auth.cooperative'), user.farmer.cooperative])
  if (user.buyer) identity.push([t('auth.businessName'), user.buyer.business_name])
  if (user.warehouses?.length) identity.push([t('ghala.warehouse'), user.warehouses.map((w) => w.name).join(', ')])

  const others = (sessions ?? []).filter((s) => !s.current)

  return (
    <div className="space-y-5">
      <PageHeader title={t('profile.title')} subtitle={t('profile.subtitle')} />

      <Card title={t('profile.account')}>
        <KeyValues items={identity} />
      </Card>

      <Card title={t('language.label')} subtitle={t('profile.languageHint')}>
        <LanguageSwitcher />
      </Card>

      <Card title={t('security.title')} subtitle={t('security.subtitle')}>
        <div className="space-y-5">
          <div className="flex flex-wrap items-start gap-3">
            <span className="flex size-10 items-center justify-center rounded-md bg-forest-100 text-forest-800">
              <Fingerprint className="size-5" aria-hidden />
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2 text-sm font-semibold">
                {t('security.biometricTitle')}
                {security?.passkeys.length ? <Badge tone="green">{t('security.on')}</Badge> : <Badge>{t('security.off')}</Badge>}
              </div>
              <p className="mt-0.5 text-[13px] text-muted">{t('security.biometricBody')}</p>
              {security?.passkeys.map((k) => (
                <div key={k.id} className="mt-2 flex items-center justify-between gap-2 rounded-md bg-sunken px-3 py-2 text-sm">
                  <span>
                    {k.label} <span className="text-xs text-muted">· {t('security.added', { date: f.date(k.created_at) })}</span>
                  </span>
                  <Button variant="ghost" size="sm" icon={Trash2} onClick={() => removeKey(k.id)} aria-label={t('security.remove')}>
                    {t('security.remove')}
                  </Button>
                </div>
              ))}
            </div>
            {supported === false ? (
              <Badge tone="stone">{t('security.notSupported')}</Badge>
            ) : (
              <Button variant={security?.passkeys.length ? 'secondary' : 'primary'} icon={Fingerprint} busy={busy === 'enrol'} disabled={!supported} onClick={enrol}>
                {security?.passkeys.length ? t('security.addAnother') : t('security.turnOn')}
              </Button>
            )}
          </div>
          <ErrorNote text={error} />
          <Notice tone="neutral">{t('security.privacyNote')}</Notice>
          <div className="flex items-start gap-3 border-t border-line pt-4">
            <span className="flex size-10 items-center justify-center rounded-md bg-sunken text-ink-soft">
              <KeyRound className="size-5" aria-hidden />
            </span>
            <div className="text-sm">
              <div className="font-semibold">{t('security.pinTitle')}</div>
              <p className="mt-0.5 text-[13px] text-muted">{t('security.pinBody')}</p>
            </div>
          </div>
        </div>
      </Card>

      <Card
        title={t('security.devicesTitle')}
        subtitle={t('security.devicesSubtitle')}
        actions={others.length > 0 && <Button variant="danger" size="sm" icon={LogOut} busy={busy === 'others'} onClick={revokeOthers}>{t('security.signOutOthers')}</Button>}
      >
        {sessionsLoading && !sessions ? (
          <Skeleton className="h-14" />
        ) : !sessions?.length ? (
          <EmptyState compact icon={ShieldCheck} title={t('security.noSessions')} />
        ) : (
          <ul className="-my-2 divide-y divide-line">
            {sessions.map((s) => {
              const Icon = /Android|iPhone|iPad/.test(s.device) ? Smartphone : Laptop
              return (
                <li key={s.id} className="flex items-center gap-3 py-3">
                  <Icon className="size-5 shrink-0 text-muted" aria-hidden />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2 text-sm font-medium">
                      {s.device}
                      {s.current && <Badge tone="green">{t('security.thisDevice')}</Badge>}
                    </div>
                    <div className="text-xs text-muted">
                      {t(`security.method.${s.login_method}`, { defaultValue: s.login_method })} · {t('security.since', { date: f.dateTime(s.started_at) })} ·{' '}
                      {t('security.lastActive', { time: f.relative(s.last_active_at) })}
                    </div>
                  </div>
                  {!s.current && (
                    <Button variant="ghost" size="sm" onClick={() => revoke(s.id)}>
                      {t('security.signOut')}
                    </Button>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </Card>

      <Button variant="secondary" icon={LogOut} onClick={logout} className="w-full sm:w-auto">
        {t('auth.logout')}
      </Button>
    </div>
  )
}
