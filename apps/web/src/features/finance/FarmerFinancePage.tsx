import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'
import { ErrorState, Loading, PageHeader, Tabs } from '../../components/ui'
import { useApi, useErrorText } from '../../lib/hooks'
import { ContestProfile, InsuranceTab, LoansTab } from './FinanceTabs'
import { ProfileView, type Profile } from './ProfileView'
import { SavingsTab, SharingTab } from './SavingsSharing'

const TABS = ['profile', 'loans', 'insurance', 'savings', 'sharing'] as const
type Tab = (typeof TABS)[number]

export function FarmerFinancePage() {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const [params, setParams] = useSearchParams()
  const tab = (TABS as readonly string[]).includes(params.get('tab') ?? '') ? (params.get('tab') as Tab) : 'profile'
  const { data: profile, loading, error, reload } = useApi<Profile>('/farmers/me/profile')

  return (
    <div>
      <PageHeader title={t('finance.title')} subtitle={t('finance.subtitle')} />
      <Tabs value={tab} onChange={(id) => setParams(id === 'profile' ? {} : { tab: id }, { replace: true })} tabs={TABS.map((id) => ({ id, label: t(`finance.tabs.${id}`) }))} />
      <div className="mt-5">
        {tab === 'profile' &&
          (loading && !profile ? (
            <Loading rows={4} />
          ) : error || !profile ? (
            <ErrorState text={errorText(error)} onRetry={reload} />
          ) : (
            <div className="space-y-5">
              <ProfileView profile={profile} />
              <ContestProfile />
            </div>
          ))}
        {tab === 'loans' && <LoansTab profile={profile} />}
        {tab === 'insurance' && <InsuranceTab profile={profile} />}
        {tab === 'savings' && <SavingsTab />}
        {tab === 'sharing' && <SharingTab />}
      </div>
    </div>
  )
}
