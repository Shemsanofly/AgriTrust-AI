import { FileSignature, Plus } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Badge, Button, Card, Dialog, EmptyState, ErrorNote, ErrorState, Field, KeyValues, Loading, Notice, PageHeader, StatusBadge, useToast } from '../../components/ui'
import { api } from '../../lib/api'
import { useApi, useErrorText, useFormat } from '../../lib/hooks'

export type Contract = {
  id: number
  crop_type: string
  quantity_kg: number
  price_per_kg: number
  total_tzs: number
  delivery_month: string
  note: string
  status: 'OFFERED' | 'ACCEPTED' | 'DECLINED' | 'CANCELLED' | 'FULFILLED'
  created_at: string
  buyer: { name: string; verified: boolean } | null
  farmer: { public_id: string; display_name: string; region: string } | null
}

type DirectoryFarmer = { public_id: string; display_name: string; region: string; cooperative: string | null; acres: number; growing: string[]; next_harvest: string | null }
type Action = 'accept' | 'decline' | 'cancel' | 'fulfil'

const CROPS = ['maize', 'beans', 'rice', 'sorghum', 'sunflower'] as const
const thisMonth = () => new Date().toISOString().slice(0, 7)

/** One contract with the actions the viewer may take. */
function ContractRow({ c, viewer, onAction }: { c: Contract; viewer: 'farmer' | 'buyer'; onAction: (c: Contract, action: Action) => void }) {
  const { t } = useTranslation()
  const f = useFormat()
  const who = viewer === 'farmer' ? c.buyer?.name : `${c.farmer?.display_name} · ${c.farmer?.public_id}`
  return (
    <li className="py-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="font-semibold">
          {t(`crops.${c.crop_type}`)} · <span className="num">{f.kg(c.quantity_kg)}</span>
        </div>
        <StatusBadge status={c.status} />
      </div>
      <p className="mt-0.5 text-[13px] text-muted">
        {who}
        {viewer === 'farmer' && c.buyer?.verified && (
          <>
            {' '}
            <Badge tone="green">{t('contracts.verifiedBuyer')}</Badge>
          </>
        )}
      </p>
      <p className="num mt-1.5 text-sm">
        {f.tzs(c.price_per_kg)}/kg · <b>{f.tzs(c.total_tzs)}</b> · {t('contracts.deliveryIn', { month: f.month(c.delivery_month) })}
      </p>
      {c.note && <p className="mt-1.5 rounded-md bg-sunken px-3 py-2 text-[13px]">“{c.note}”</p>}
      <div className="mt-3 flex flex-wrap gap-2 empty:hidden">
        {viewer === 'farmer' && c.status === 'OFFERED' && (
          <>
            <Button size="sm" onClick={() => onAction(c, 'accept')}>
              {t('contracts.accept')}
            </Button>
            <Button size="sm" variant="secondary" onClick={() => onAction(c, 'decline')}>
              {t('contracts.decline')}
            </Button>
          </>
        )}
        {viewer === 'buyer' && c.status === 'OFFERED' && (
          <Button size="sm" variant="secondary" onClick={() => onAction(c, 'cancel')}>
            {t('contracts.withdraw')}
          </Button>
        )}
        {viewer === 'buyer' && c.status === 'ACCEPTED' && (
          <Button size="sm" variant="secondary" onClick={() => onAction(c, 'fulfil')}>
            {t('contracts.markDelivered')}
          </Button>
        )}
      </div>
    </li>
  )
}

/** Contract list plus the confirm step for each action. */
function ContractList({ viewer, contracts, onChanged, empty }: { viewer: 'farmer' | 'buyer'; contracts: Contract[]; onChanged: () => void; empty: { title: string; body?: string } }) {
  const { t } = useTranslation()
  const f = useFormat()
  const toast = useToast()
  const errorText = useErrorText()
  const [pending, setPending] = useState<{ c: Contract; action: Action } | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const confirm = async () => {
    if (!pending) return
    setBusy(true)
    setError(null)
    try {
      await api(`/contracts/${pending.c.id}`, { method: 'PATCH', body: { action: pending.action } })
      toast(t(`contracts.done.${pending.action}`))
      setPending(null)
      onChanged()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  if (!contracts.length) return <EmptyState compact icon={FileSignature} title={empty.title} body={empty.body} />
  // Offers waiting for an answer first, then the rest newest first.
  const sorted = [...contracts].sort((a, b) => Number(b.status === 'OFFERED') - Number(a.status === 'OFFERED'))
  return (
    <>
      <ul className="-my-4 divide-y divide-line">
        {sorted.map((c) => (
          <ContractRow key={c.id} c={c} viewer={viewer} onAction={(c, action) => (setError(null), setPending({ c, action }))} />
        ))}
      </ul>
      <Dialog
        open={pending != null}
        onClose={() => setPending(null)}
        title={pending ? t(`contracts.confirm.${pending.action}`) : ''}
        footer={
          <>
            <Button variant="ghost" onClick={() => setPending(null)}>
              {t('common.cancel')}
            </Button>
            <Button variant={pending?.action === 'decline' || pending?.action === 'cancel' ? 'danger' : 'primary'} busy={busy} onClick={confirm}>
              {pending && t(`contracts.${pending.action === 'cancel' ? 'withdraw' : pending.action === 'fulfil' ? 'markDelivered' : pending.action}`)}
            </Button>
          </>
        }
      >
        {pending && (
          <div className="space-y-4">
            <KeyValues
              items={[
                [t('contracts.crop'), t(`crops.${pending.c.crop_type}`)],
                [t('contracts.quantity'), f.kg(pending.c.quantity_kg)],
                [t('contracts.price'), `${f.tzs(pending.c.price_per_kg)}/kg`],
                [t('contracts.total'), f.tzs(pending.c.total_tzs)],
                [t('contracts.delivery'), f.month(pending.c.delivery_month)],
                [viewer === 'farmer' ? t('contracts.buyer') : t('contracts.farmer'), viewer === 'farmer' ? pending.c.buyer?.name : pending.c.farmer?.display_name],
              ]}
            />
            {pending.action === 'accept' && <Notice tone="neutral">{t('contracts.acceptNote')}</Notice>}
            <ErrorNote text={error} />
          </div>
        )}
      </Dialog>
    </>
  )
}

/** Farmer side: offers from buyers for the coming harvest (shown on the Market page). */
export function FarmerContracts({ contracts, onChanged }: { contracts: Contract[]; onChanged: () => void }) {
  const { t } = useTranslation()
  return (
    <div className="space-y-4">
      <Notice tone="neutral">{t('contracts.farmerNote')}</Notice>
      <Card>
        <ContractList viewer="farmer" contracts={contracts} onChanged={onChanged} empty={{ title: t('contracts.noneFarmer'), body: t('contracts.noneFarmerBody') }} />
      </Card>
    </div>
  )
}

/** Buyer side: offer contracts for future harvests and follow them up. */
export function BuyerContractsPage() {
  const { t } = useTranslation()
  const f = useFormat()
  const errorText = useErrorText()
  const { data: contracts, loading, error, reload } = useApi<Contract[]>('/contracts')
  const [offering, setOffering] = useState(false)
  const active = (contracts ?? []).filter((c) => c.status === 'ACCEPTED')

  return (
    <div>
      <PageHeader
        title={t('contracts.title')}
        subtitle={t('contracts.buyerSubtitle')}
        actions={
          <Button icon={Plus} onClick={() => setOffering(true)}>
            {t('contracts.offer')}
          </Button>
        }
      />
      {active.length > 0 && (
        <p className="num mb-4 text-sm text-muted">
          {t('contracts.activeSummary', { count: active.length, kg: f.kg(active.reduce((s, c) => s + c.quantity_kg, 0)), value: f.tzs(active.reduce((s, c) => s + c.total_tzs, 0)) })}
        </p>
      )}
      {loading && !contracts ? (
        <Loading />
      ) : error ? (
        <ErrorState text={errorText(error)} onRetry={reload} />
      ) : (
        <Card>
          <ContractList viewer="buyer" contracts={contracts ?? []} onChanged={reload} empty={{ title: t('contracts.noneBuyer'), body: t('contracts.noneBuyerBody') }} />
        </Card>
      )}
      <OfferDialog open={offering} onClose={() => setOffering(false)} onDone={() => (setOffering(false), reload())} />
    </div>
  )
}

function OfferDialog({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: () => void }) {
  const { t } = useTranslation()
  const f = useFormat()
  const toast = useToast()
  const errorText = useErrorText()
  const { data: farmers } = useApi<DirectoryFarmer[]>(open ? '/contracts/farmers' : null)
  const [form, setForm] = useState({ farmer: '', crop: '', kg: '', price: '', month: '', note: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const farmer = farmers?.find((x) => x.public_id === form.farmer)
  const crop = form.crop || farmer?.growing[0] || 'maize'
  const month = form.month || farmer?.next_harvest?.slice(0, 7) || ''
  const kg = Number(form.kg.replace(/[, ]/g, ''))
  const price = Number(form.price.replace(/[, ]/g, ''))
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value })

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!farmer) return setError(t('contracts.pickFarmer'))
    if (!(kg > 0) || !(price > 0)) return setError(t('validation.amount'))
    if (!month || month < thisMonth()) return setError(t('contracts.pickMonth'))
    setBusy(true)
    setError(null)
    try {
      await api('/contracts', { method: 'POST', body: { farmer_id: farmer.public_id, crop_type: crop, quantity_kg: kg, price_per_kg: price, delivery_month: month, note: form.note.trim() } })
      toast(t('contracts.sent', { name: farmer.display_name }))
      setForm({ farmer: '', crop: '', kg: '', price: '', month: '', note: '' })
      onDone()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title={t('contracts.offerTitle')}>
      <form onSubmit={submit} className="space-y-4" noValidate>
        <Field label={t('contracts.farmer')}>
          <select className="input" value={form.farmer} onChange={(e) => setForm({ ...form, farmer: e.target.value, crop: '', month: '' })}>
            <option value="">{t('contracts.chooseFarmer')}</option>
            {farmers?.map((x) => (
              <option key={x.public_id} value={x.public_id}>
                {x.display_name} · {x.region} · {x.acres} {t('farm.acres')}
              </option>
            ))}
          </select>
        </Field>
        {farmer && (
          <p className="-mt-2 text-xs text-muted">
            {farmer.growing.length ? t('contracts.growing', { crops: farmer.growing.map((c) => t(`crops.${c}`)).join(', ') }) : t('contracts.notGrowing')}
            {farmer.next_harvest ? ` · ${t('contracts.nextHarvest', { date: f.date(farmer.next_harvest) })}` : ''}
          </p>
        )}
        <div className="grid grid-cols-2 gap-3">
          <Field label={t('contracts.crop')}>
            <select className="input" value={crop} onChange={set('crop')}>
              {CROPS.map((c) => (
                <option key={c} value={c}>
                  {t(`crops.${c}`)}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t('contracts.delivery')}>
            <input className="input" type="month" min={thisMonth()} value={month} onChange={set('month')} />
          </Field>
          <Field label={t('contracts.quantity')}>
            <input className="input num" inputMode="numeric" value={form.kg} onChange={set('kg')} placeholder="1000" />
          </Field>
          <Field label={t('contracts.pricePerKg')}>
            <input className="input num" inputMode="numeric" value={form.price} onChange={set('price')} placeholder="800" />
          </Field>
        </div>
        {kg > 0 && price > 0 && <p className="num text-sm">{t('contracts.totalValue', { value: f.tzs(kg * price) })}</p>}
        <Field label={t('contracts.note')} optional>
          <textarea className="input min-h-20" value={form.note} onChange={set('note')} maxLength={300} placeholder={t('contracts.notePlaceholder')} />
        </Field>
        <ErrorNote text={error} />
        <Button type="submit" busy={busy} className="w-full">
          {t('contracts.send')}
        </Button>
      </form>
    </Dialog>
  )
}
