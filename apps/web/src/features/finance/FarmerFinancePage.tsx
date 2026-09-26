import { ArrowLeft } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'
import { Button, ErrorState, Loading, PageHeader, Tabs } from '../../components/ui'
import { useApi, useErrorText } from '../../lib/hooks'
import { InsuranceTab, LoansTab } from './FinanceTabs'
import { FinancialStatus } from './FinancialStatus'
import type { Profile } from './ProfileView'
import { SavingsTab, SharingTab } from './SavingsSharing'

const TABS = ['status', 'loans', 'savings', 'insurance'] as const
/** Data sharing is reached from the status tab, not the tab bar. */
const ALL = [...TABS, 'sharing'] as const
type Tab = (typeof ALL)[number]

export function FarmerFinancePage() {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const [params, setParams] = useSearchParams()
  const tab = (ALL as readonly string[]).includes(params.get('tab') ?? '') ? (params.get('tab') as Tab) : 'status'
  const open = (id: Tab) => setParams(id === 'status' ? {} : { tab: id }, { replace: true })
  const { data: profile, loading, error, reload } = useApi<Profile>('/farmers/me/profile')

  return (
    <div>
      <PageHeader title={t('finance.title')} subtitle={t('finance.subtitle')} />
      <Tabs value={tab === 'sharing' ? 'status' : tab} onChange={open} tabs={TABS.map((id) => ({ id, label: t(`finance.tabs.${id}`) }))} />
      <div className="mt-5">
        {tab === 'status' &&
          (loading && !profile ? <Loading rows={4} /> : error || !profile ? <ErrorState text={errorText(error)} onRetry={reload} /> : <FinancialStatus profile={profile} onOpen={open} />)}
        {tab === 'loans' && <LoansTab profile={profile} />}
        {tab === 'savings' && <SavingsTab />}
        {tab === 'insurance' && <InsuranceTab profile={profile} />}
        {tab === 'sharing' && (
          <div className="space-y-4">
            <Button variant="ghost" size="sm" icon={ArrowLeft} onClick={() => open('status')}>
              {t('finance.tabs.status')}
            </Button>
            <SharingTab />
          </div>
        )}
      </div>
    </div>
  )
}
