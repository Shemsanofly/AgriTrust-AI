import { browserSupportsWebAuthn, platformAuthenticatorIsAvailable, startAuthentication, startRegistration } from '@simplewebauthn/browser'
import { api } from './api'

/* Device biometrics through WebAuthn passkeys. The fingerprint / face check happens on
   the phone; only a public key and signed challenges reach our server. */

export async function biometricAvailable(): Promise<boolean> {
  try {
    return browserSupportsWebAuthn() && (await platformAuthenticatorIsAvailable())
  } catch {
    return false
  }
}

const parse = (raw: unknown) => (typeof raw === 'string' ? JSON.parse(raw) : raw)

export async function enrolBiometric(label: string) {
  const optionsJSON = parse(await api('/auth/webauthn/register/begin', { method: 'POST' }))
  const credential = await startRegistration({ optionsJSON })
  return api('/auth/webauthn/register/finish', { method: 'POST', body: { credential, label } })
}

export async function biometricSignIn(phone: string) {
  const optionsJSON = parse(await api('/auth/webauthn/login/begin', { method: 'POST', body: { phone }, auth: false }))
  const credential = await startAuthentication({ optionsJSON })
  return api('/auth/webauthn/login/finish', { method: 'POST', body: { phone, credential }, auth: false })
}

/** Returns a short-lived token that the API accepts in place of the PIN. */
export async function biometricConfirm(): Promise<string> {
  const optionsJSON = parse(await api('/auth/webauthn/stepup/begin', { method: 'POST' }))
  const credential = await startAuthentication({ optionsJSON })
  const res = await api<{ confirm_pin: string }>('/auth/webauthn/stepup/finish', { method: 'POST', body: { credential } })
  return res.confirm_pin
}
