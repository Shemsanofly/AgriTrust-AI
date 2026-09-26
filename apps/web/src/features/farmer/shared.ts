import type { Bi } from '../../lib/hooks'

export type Crop = {
  id: number
  farm_id: number
  crop_type: string
  variety?: string
  growth_stage: string
  planting_date: string
  expected_harvest_date?: string
}

export type Farm = {
  id: number
  name: string
  region: string
  lat: number
  lon: number
  acreage: number
  soil_type: string
  irrigation_type: string
  soil_ph?: number | null
  soil_nitrogen?: string | null
  soil_phosphorus?: string | null
  soil_potassium?: string | null
  organic_matter_pct?: number | null
  soil_source?: string | null
  created_at?: string
  crops: Crop[]
  sensors: { device_id: string; type: string; simulated: boolean; last_seen_at: string | null }[]
  latest: Record<string, { value: number; ts: string; quality_flag: string }>
}

export type Advice = {
  id: number
  action: 'IRRIGATE' | 'SKIP_RAIN' | 'NO_ACTION' | 'CHECK_SENSOR'
  amount_mm: number
  headline: Bi
  when: Bi
  reasons: Bi[]
  followed: boolean | null
  model_version: string
  created_at: string
  inputs: Record<string, any>
}

export type Weather = { simulated: boolean; source: string; days: { date: string; rain_mm: number; et0_mm: number; tmax_c: number }[] }

export type Batch = {
  id: string
  crop_type: string
  harvest_date: string
  quantity_kg: number
  available_kg: number
  grade: string | null
  status: string
  listed: boolean
  price_per_kg: number | null
  qr_url: string
  created_at: string
  days_in_storage: number | null
  warehouse: { id: number; public_id: string; name: string; region: string } | null
  receipt: { id: string; status: string; quantity_kg: number; released_kg: number; grade: string; date_in: string; bay: string; created_at: string } | null
  risk: { level: string; headline: Bi; drivers: Bi[]; action: Bi; stats: Record<string, number>; model_version: string } | null
  proofs?: { entity_type: string; entity_id: string; mode: string; tx_hash: string; block_number: number; anchored_at: string }[]
  storage_records?: { id: number; window_start: string; window_end: string; risk_level: string; temp_avg: number; rh_avg: number; reading_count: number; merkle_root: string }[]
}

/** Ideal volumetric soil moisture used for the Dry / Good / Wet label. */
export const MOISTURE_IDEAL = { min: 25, max: 45 }

export const STAGES = ['initial', 'vegetative', 'flowering', 'maturity'] as const

export function moistureState(v?: number | null): 'dry' | 'good' | 'wet' | null {
  if (v == null) return null
  if (v < MOISTURE_IDEAL.min) return 'dry'
  if (v > MOISTURE_IDEAL.max) return 'wet'
  return 'good'
}

export function seasonProgress(c: Crop): number | null {
  if (c.growth_stage === 'harvested') return 100
  if (!c.expected_harvest_date) return null
  const start = new Date(c.planting_date).getTime()
  const end = new Date(c.expected_harvest_date).getTime()
  if (!(end > start)) return null
  return Math.round(Math.min(100, Math.max(0, ((Date.now() - start) / (end - start)) * 100)))
}

export const daysUntil = (iso?: string | null) => (iso ? Math.ceil((new Date(iso).getTime() - Date.now()) / 86_400_000) : null)
