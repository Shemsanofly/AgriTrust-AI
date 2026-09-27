import { lazy, Suspense, type ComponentType } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Loading } from './components/ui'
import { LoginPage, RegisterPage } from './features/auth/AuthPages'
import { useAuth, type Role } from './lib/auth'

// Each role only downloads the screens it uses (low-bandwidth friendly).
const named = <K extends string>(loader: () => Promise<Record<K, ComponentType<any>>>, name: K) =>
  lazy(() => loader().then((m) => ({ default: m[name] })))

const account = () => import('./features/account/ProfilePage')
const alerts = () => import('./features/account/AlertsPage')
const farmer = () => import('./features/farmer/HomePage')
const myFarm = () => import('./features/farmer/MyFarmPage')
const ghala = () => import('./features/ghala/FarmerGhalaPage')
const batch = () => import('./features/ghala/BatchDetailPage')
const warehouse = () => import('./features/ghala/WarehousePages')
const orders = () => import('./features/orders/OrdersPages')
const finance = () => import('./features/finance/FarmerFinancePage')
const partners = () => import('./features/finance/PartnerPortals')
const market = () => import('./features/marketplace/Marketplace')
const buyer = () => import('./features/marketplace/BuyerPages')
const contracts = () => import('./features/contracts/ContractsPages')
const verify = () => import('./features/verify/VerifyPage')
const admin = () => import('./features/admin/AdminPages')

const ProfilePage = named(account, 'ProfilePage')
const ReportsPage = named(() => import('./features/account/ReportsPage'), 'ReportsPage')
const AlertsPage = named(alerts, 'AlertsPage')
const FarmerHome = named(farmer, 'FarmerHome')
const MyFarmPage = named(myFarm, 'MyFarmPage')
const FarmerGhalaPage = named(ghala, 'FarmerGhalaPage')
const BatchDetailPage = named(batch, 'BatchDetailPage')
const WarehouseOverview = named(warehouse, 'WarehouseOverview')
const WarehouseStockPage = named(warehouse, 'WarehouseStockPage')
const IntakePage = named(warehouse, 'IntakePage')
const FarmerMarketPage = named(orders, 'FarmerMarketPage')
const BuyerOrdersPage = named(orders, 'BuyerOrdersPage')
const WarehouseOrdersPage = named(orders, 'WarehouseOrdersPage')
const FarmerFinancePage = named(finance, 'FarmerFinancePage')
const LenderOverview = named(partners, 'LenderOverview')
const ApplicationsPage = named(partners, 'ApplicationsPage')
const ApplicationDetail = named(partners, 'ApplicationDetail')
const FarmersPage = named(partners, 'FarmersPage')
const RiskProfilesPage = named(partners, 'RiskProfilesPage')
const RiskProfileDetail = named(partners, 'RiskProfileDetail')
const LoanBookPage = named(partners, 'LoanBookPage')
const InsurerOverview = named(partners, 'InsurerOverview')
const PoliciesPage = named(partners, 'PoliciesPage')
const FarmRiskPage = named(partners, 'FarmRiskPage')
const ClaimsPage = named(partners, 'ClaimsPage')
const Marketplace = named(market, 'Marketplace')
const ListingDetail = named(market, 'ListingDetail')
const VerifiedBatchesPage = named(buyer, 'VerifiedBatchesPage')
const SuppliersPage = named(buyer, 'SuppliersPage')
const BuyerContractsPage = named(contracts, 'BuyerContractsPage')
const PaymentsPage = named(buyer, 'PaymentsPage')
const VerifyPage = named(verify, 'VerifyPage')
const ScanPage = named(verify, 'ScanPage')
const AdminOverview = named(admin, 'AdminOverview')
const FraudPage = named(admin, 'FraudPage')
const AuditPage = named(admin, 'AuditPage')
const UsersPage = named(admin, 'UsersPage')
const SmsPage = named(admin, 'SmsPage')
const DemoToolsPage = named(admin, 'DemoToolsPage')

/** Routes per role; navigation in app/nav.ts mirrors these. */
function roleRoutes(role: Role) {
  switch (role) {
    case 'FARMER':
      return (
        <>
          <Route index element={<FarmerHome />} />
          <Route path="farm" element={<MyFarmPage />} />
          <Route path="ghala" element={<FarmerGhalaPage />} />
          <Route path="ghala/:batchId" element={<BatchDetailPage backTo="/ghala" />} />
          <Route path="market" element={<FarmerMarketPage />} />
          <Route path="finance" element={<FarmerFinancePage />} />
          <Route path="alerts" element={<AlertsPage />} />
        </>
      )
    case 'BUYER':
      return (
        <>
          <Route index element={<Marketplace />} />
          <Route path="market/:batchId" element={<ListingDetail />} />
          <Route path="orders" element={<BuyerOrdersPage />} />
          <Route path="contracts" element={<BuyerContractsPage />} />
          <Route path="verified" element={<VerifiedBatchesPage />} />
          <Route path="suppliers" element={<SuppliersPage />} />
          <Route path="payments" element={<PaymentsPage />} />
        </>
      )
    case 'WAREHOUSE_OPERATOR':
      return (
        <>
          <Route index element={<WarehouseOverview />} />
          <Route path="stock" element={<WarehouseStockPage />} />
          <Route path="stock/:batchId" element={<BatchDetailPage backTo="/stock" />} />
          <Route path="intake" element={<IntakePage />} />
          <Route path="orders" element={<WarehouseOrdersPage />} />
          <Route path="alerts" element={<AlertsPage />} />
        </>
      )
    case 'LENDER':
      return (
        <>
          <Route index element={<LenderOverview />} />
          <Route path="farmers" element={<FarmersPage />} />
          <Route path="applications" element={<ApplicationsPage />} />
          <Route path="applications/:id" element={<ApplicationDetail />} />
          <Route path="risk-profiles" element={<RiskProfilesPage />} />
          <Route path="risk-profiles/:farmerId" element={<RiskProfileDetail back="/risk-profiles" />} />
          <Route path="loans" element={<LoanBookPage />} />
        </>
      )
    case 'INSURER':
      return (
        <>
          <Route index element={<InsurerOverview />} />
          <Route path="policies" element={<PoliciesPage />} />
          <Route path="farm-risk" element={<FarmRiskPage />} />
          <Route path="farm-risk/:farmerId" element={<RiskProfileDetail back="/farm-risk" />} />
          <Route path="claims" element={<ClaimsPage />} />
        </>
      )
    case 'ADMIN':
      return (
        <>
          <Route index element={<AdminOverview />} />
          <Route path="fraud" element={<FraudPage />} />
          <Route path="audit" element={<AuditPage />} />
          <Route path="users" element={<UsersPage />} />
          <Route path="sms" element={<SmsPage />} />
          <Route path="demo" element={<DemoToolsPage />} />
        </>
      )
  }
}

export default function App() {
  const { user, loading } = useAuth()
  if (loading)
    return (
      <div className="mx-auto max-w-md p-6">
        <Loading />
      </div>
    )
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-5xl p-6">
          <Loading />
        </div>
      }
    >
      <Routes>
        {!user ? (
          <>
            <Route path="/verify/:id" element={<VerifyPage />} />
            <Route path="/scan" element={<ScanPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="*" element={<Navigate to="/login" replace />} />
          </>
        ) : (
          <Route element={<Layout />}>
            {roleRoutes(user.role)}
            <Route path="verify/:id" element={<VerifyPage />} />
            <Route path="scan" element={<ScanPage />} />
            <Route path="profile" element={<ProfilePage />} />
            <Route path="reports" element={<ReportsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        )}
      </Routes>
    </Suspense>
  )
}
