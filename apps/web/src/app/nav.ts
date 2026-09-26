import {
  Bell,
  Boxes,
  CloudSun,
  FileCheck2,
  FileText,
  Flag,
  Gauge,
  HandCoins,
  House,
  Landmark,
  LayoutDashboard,
  MessageSquareText,
  Package,
  PackagePlus,
  ScrollText,
  ShieldCheck,
  Sprout,
  Store,
  FlaskConical,
  Truck,
  Umbrella,
  Users,
  Wallet,
  Warehouse,
  type LucideIcon,
} from 'lucide-react'
import type { Role } from '../lib/auth'

export type NavItem = { to: string; key: string; icon: LucideIcon; badge?: 'alerts' }

/** Primary navigation per role. The first five appear in the phone tab bar; the rest
 * go under "More". Profile & security is always in the account menu. */
export const NAV: Record<Role, NavItem[]> = {
  FARMER: [
    { to: '/', key: 'nav.home', icon: House },
    { to: '/farm', key: 'nav.myFarm', icon: Sprout },
    { to: '/ghala', key: 'nav.ghala', icon: Warehouse },
    { to: '/market', key: 'nav.market', icon: Store },
    { to: '/finance', key: 'nav.finance', icon: Landmark },
  ],
  BUYER: [
    { to: '/', key: 'nav.marketplace', icon: Store },
    { to: '/orders', key: 'nav.myOrders', icon: Package },
    { to: '/verified', key: 'nav.verifiedBatches', icon: ShieldCheck },
    { to: '/suppliers', key: 'nav.suppliers', icon: Users },
    { to: '/payments', key: 'nav.payments', icon: Wallet },
  ],
  WAREHOUSE_OPERATOR: [
    { to: '/', key: 'nav.overview', icon: LayoutDashboard },
    { to: '/stock', key: 'nav.stock', icon: Boxes },
    { to: '/intake', key: 'nav.intake', icon: PackagePlus },
    { to: '/orders', key: 'nav.releases', icon: Truck },
    { to: '/alerts', key: 'nav.alerts', icon: Bell, badge: 'alerts' },
  ],
  LENDER: [
    { to: '/', key: 'nav.overview', icon: LayoutDashboard },
    { to: '/farmers', key: 'nav.farmers', icon: Users },
    { to: '/applications', key: 'nav.applications', icon: FileText },
    { to: '/risk-profiles', key: 'nav.riskProfiles', icon: Gauge },
    { to: '/loans', key: 'nav.loans', icon: HandCoins },
  ],
  INSURER: [
    { to: '/', key: 'nav.overview', icon: LayoutDashboard },
    { to: '/policies', key: 'nav.policies', icon: FileCheck2 },
    { to: '/farm-risk', key: 'nav.farmRisk', icon: CloudSun },
    { to: '/claims', key: 'nav.claims', icon: Umbrella },
  ],
  ADMIN: [
    { to: '/', key: 'nav.overview', icon: LayoutDashboard },
    { to: '/fraud', key: 'nav.fraudAlerts', icon: Flag },
    { to: '/audit', key: 'nav.audit', icon: ScrollText },
    { to: '/users', key: 'nav.users', icon: Users },
    { to: '/sms', key: 'nav.sms', icon: MessageSquareText },
    { to: '/demo', key: 'nav.demoTools', icon: FlaskConical },
  ],
}
