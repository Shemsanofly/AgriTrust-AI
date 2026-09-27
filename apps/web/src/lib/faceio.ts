import { api } from './api'

/** FACEIO face sign-in (https://faceio.net). The widget script is only downloaded when
 * someone actually uses face sign-in, so slow connections don't pay for it. */

type FaceIO = {
  enroll: (opts: { locale?: string; payload?: Record<string, unknown> }) => Promise<{ facialId: string }>
  authenticate: (opts: { locale?: string }) => Promise<{ facialId: string }>
  restartSession: () => void
}

declare global {
  interface Window {
    faceIO?: new (publicId: string) => FaceIO
    fioErrCode?: Record<string, number>
  }
}

let config: Promise<{ enabled: boolean; public_id: string | null }> | null = null
let instance: Promise<FaceIO> | null = null

export function faceConfig() {
  config ??= api<{ enabled: boolean; public_id: string | null }>('/auth/face/config', { auth: false }).catch(() => ({ enabled: false, public_id: null }))
  return config
}

function loadScript(): Promise<void> {
  if (window.faceIO) return Promise.resolve()
  return new Promise((resolve, reject) => {
    const s = document.createElement('script')
    s.src = 'https://cdn.faceio.net/fio.js'
    s.async = true
    s.onload = () => resolve()
    s.onerror = () => reject(new Error('faceio_script'))
    document.head.appendChild(s)
  })
}

async function faceio(): Promise<FaceIO> {
  instance ??= (async () => {
    const { public_id } = await faceConfig()
    if (!public_id) throw new Error('face_disabled')
    await loadScript()
    return new window.faceIO!(public_id)
  })().catch((err) => {
    instance = null
    throw err
  })
  return instance
}

/** Runs a FACEIO step; after a failure FACEIO needs a fresh session before the next try. */
async function run<T>(step: (fio: FaceIO) => Promise<T>): Promise<T> {
  const fio = await faceio()
  try {
    return await step(fio)
  } catch (err) {
    fio.restartSession()
    throw err
  }
}

export const enrollFace = () => run((fio) => fio.enroll({ locale: 'auto' })).then((r) => r.facialId)
export const recogniseFace = () => run((fio) => fio.authenticate({ locale: 'auto' })).then((r) => r.facialId)

/** Translation key under `face.err.*` for a FACEIO error code (FACEIO rejects with a number). */
export function faceErrorKey(err: unknown): string {
  if (err instanceof Error && err.message === 'faceio_script') return 'offline'
  const codes = window.fioErrCode ?? {}
  const name = Object.keys(codes).find((k) => codes[k] === err)
  switch (name) {
    case 'PERMISSION_REFUSED':
      return 'camera'
    case 'NO_FACES_DETECTED':
    case 'MANY_FACES':
      return 'noFace'
    case 'UNRECOGNIZED_FACE':
      return 'unknown'
    case 'FACE_DUPLICATION':
      return 'duplicate'
    case 'TIMEOUT':
    case 'SESSION_EXPIRED':
      return 'timeout'
    case 'NETWORK_IO':
      return 'offline'
    case 'EMPTY_ORIGIN':
    case 'FORBIDDDEN_ORIGIN': // sic: FACEIO's own spelling
    case 'UNAUTHORIZED':
      return 'setup'
    case 'TERMS_NOT_ACCEPTED':
      return 'cancelled'
    default:
      return 'failed'
  }
}
