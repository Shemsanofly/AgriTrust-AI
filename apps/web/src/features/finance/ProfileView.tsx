import { useTranslation } from 'react-i18next'
import { Badge, Card, Stat } from '../../components/ui'
import { useBi, useFormat, type Bi } from '../../lib/hooks'

export type Profile = {
  farmer_id: string
  display_name: string
  region: string
  generated_at: string
  model_version: string
  risk_band: 'LOW' | 'MEDIUM' | 'HIGH'
  score: number
  positive_factors: Bi[]
  risk_factors: Bi[]
  cash_flow_estimate: {
    next_harvest_month: string | null
    expected_income_range_tzs: [number, number] | null
    expected_yield_kg?: number
    price_per_kg_tzs?: number
    price_source?: string
  }
  suggested_products: { type: string; reason: Bi; max_amount_tzs?: number; repayment_month?: string; status?: string }[]
  disclaimer: Bi
}

/** The explainable profile: factors and reasons, never an unexplained number. */
export function ProfileView({ profile }: { profile: Profile }) {
  const { t } = useTranslation()
  const bi = useBi()
  const f = useFormat()
  const band = { LOW: ['green', '🟢'], MEDIUM: ['amber', '🟡'], HIGH: ['red', '🔴'] }[profile.risk_band] as ['green' | 'amber' | 'red', string]
  const flow = profile.cash_flow_estimate

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <div className="text-sm text-stone-500">
              {profile.display_name} · {profile.farmer_id} · {profile.region}
            </div>
            <div className="mt-1 flex items-center gap-2 text-xl font-bold">
              {band[1]} {t('profile.riskBand')}: <Badge tone={band[0]}>{t(`risk.${profile.risk_band}`)}</Badge>
            </div>
          </div>
          <div className="text-right text-xs text-stone-500">
            <div>{t('profile.score')}: {f.num(profile.score)} / 100</div>
            <div>{profile.model_version}</div>
            <div>{f.dateTime(profile.generated_at)}</div>
          </div>
        </div>
        <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">⚖️ {bi(profile.disclaimer)}</p>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2">
        <Card title={`✅ ${t('profile.positive')}`}>
          {profile.positive_factors.length ? (
            <ul className="list-disc space-y-1 pl-5 text-sm">
              {profile.positive_factors.map((x, i) => (
                <li key={i}>{bi(x)}</li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-stone-500">—</p>
          )}
        </Card>
        <Card title={`⚠️ ${t('profile.risks')}`}>
          {profile.risk_factors.length ? (
            <ul className="list-disc space-y-1 pl-5 text-sm">
              {profile.risk_factors.map((x, i) => (
                <li key={i}>{bi(x)}</li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-stone-500">—</p>
          )}
        </Card>
      </div>

      <Card title={`📅 ${t('profile.cashFlow')}`}>
        {flow.expected_income_range_tzs ? (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Stat label={t('profile.nextHarvest')} value={flow.next_harvest_month} />
            <Stat label={t('profile.expectedYield')} value={`${f.num(flow.expected_yield_kg)} kg`} />
            <Stat label={t('profile.price')} value={f.tzs(flow.price_per_kg_tzs)} sub={t(`profile.priceSource.${flow.price_source}`)} />
            <Stat label={t('profile.income')} value={`${f.num(flow.expected_income_range_tzs[0] / 1e6, 1)}–${f.num(flow.expected_income_range_tzs[1] / 1e6, 1)}M`} sub="TZS" />
          </div>
        ) : (
          <p className="text-sm text-stone-500">{t('profile.noCashFlow')}</p>
        )}
      </Card>

      <Card title={`💡 ${t('profile.products')}`}>
        <ul className="space-y-2">
          {profile.suggested_products.map((p, i) => (
            <li key={i} className="rounded-xl bg-stone-50 p-3 text-sm">
              <div className="flex flex-wrap items-center gap-2 font-semibold">
                {t(`products.${p.type}`)}
                {p.status === 'FUTURE' && <Badge>{t('common.future')}</Badge>}
                {p.max_amount_tzs != null && <span className="font-normal text-stone-600">≤ {f.tzs(p.max_amount_tzs)}</span>}
              </div>
              <div className="text-stone-600">{bi(p.reason)}</div>
            </li>
          ))}
          {!profile.suggested_products.length && <li className="text-sm text-stone-500">—</li>}
        </ul>
      </Card>
    </div>
  )
}
