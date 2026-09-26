import { CheckCircle2 } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { AlertRow, type Alert } from '../../components/AlertsPanel'
import { Card, EmptyState, ErrorState, Loading, PageHeader, Tabs } from '../../components/ui'
import { api } from '../../lib/api'
import { useApi, useErrorText } from '../../lib/hooks'

export function AlertsPage() {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const { data, loading, error, reload } = useApi<Alert[]>('/alerts')
  const [tab, setTab] = useState<'open' | 'all'>('open')
  const open = (data ?? []).filter((a) => !a.resolved_at)
  const rows = tab === 'open' ? open : data ?? []

  const resolve = async (id: number) => {
    await api(`/alerts/${id}/resolve`, { method: 'POST' })
    reload()
  }

  return (
    <div>
      <PageHeader title={t('alerts.title')} subtitle={t('alerts.subtitle')} />
      <Tabs
        value={tab}
        onChange={setTab}
        tabs={[
          { id: 'open', label: t('alerts.open'), count: open.length },
          { id: 'all', label: t('alerts.all'), count: data?.length },
        ]}
      />
      <Card className="mt-4">
        {loading && !data ? (
          <Loading />
        ) : error ? (
          <ErrorState text={errorText(error)} onRetry={reload} />
        ) : rows.length === 0 ? (
          <EmptyState icon={CheckCircle2} title={t('alerts.none')} body={t('alerts.noneBody')} />
        ) : (
          <ul className="-my-3 divide-y divide-line">
            {rows.map((a) => (
              <AlertRow key={a.id} alert={a} onResolve={resolve} />
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
