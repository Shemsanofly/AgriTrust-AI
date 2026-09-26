import { lazy, Suspense, type ComponentType } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Loading } from './components/ui'
import { LoginPage, RegisterPage } from './features/auth/AuthPages'
import { useAuth } from './lib/auth'

// Each role only downloads the screens it uses (low-bandwidth friendly).
const named = <K extends string>(loader: () => Promise<Record<K, ComponentType>>, name: K) =>
  lazy(() => loader().then((m) => ({ default: m[name] })))
const AdminPage = named(() => import('./features/admin/AdminPage'), 'AdminPage')
const FarmDashboard = named(() => import('./features/farm/FarmDashboard'), 'FarmDashboard')
const KifedhaPage = named(() => import('./features/finance/KifedhaPage'), 'KifedhaPage')
const LenderPortal = named(() => import('./features/finance/PartnerPortals'), 'LenderPortal')
const InsurerPortal = named(() => import('./features/finance/PartnerPortals'), 'InsurerPortal')
const BatchesPage = named(() => import('./features/ghala/BatchesPage'), 'BatchesPage')
const WarehouseDashboard = named(() => import('./features/ghala/WarehouseDashboard'), 'WarehouseDashboard')
const Marketplace = named(() => import('./features/marketplace/Marketplace'), 'Marketplace')
const ListingDetail = named(() => import('./features/marketplace/Marketplace'), 'ListingDetail')
const OrdersPage = named(() => import('./features/orders/OrdersPage'), 'OrdersPage')
const VerifyPage = named(() => import('./features/verify/VerifyPage'), 'VerifyPage')

function Home() {
  const { user } = useAuth()
  switch (user?.role) {
    case 'FARMER':
      return <FarmDashboard />
    case 'BUYER':
      return <Marketplace />
    case 'WAREHOUSE_OPERATOR':
      return <WarehouseDashboard />
    case 'LENDER':
      return <LenderPortal />
    case 'INSURER':
      return <InsurerPortal />
    case 'ADMIN':
      return <AdminPage />
    default:
      return null
  }
}

export default function App() {
  const { user, loading } = useAuth()
  if (loading) return <Loading />
  return (
    <Suspense fallback={<Loading />}>
    <Routes>
      <Route path="/verify/:id" element={<VerifyPage />} />
      {!user ? (
        <>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </>
      ) : (
        <Route element={<Layout />}>
          <Route index element={<Home />} />
          {user.role === 'FARMER' && <Route path="/batches" element={<BatchesPage />} />}
          {user.role === 'FARMER' && <Route path="/kifedha" element={<KifedhaPage />} />}
          {user.role === 'BUYER' && <Route path="/market/:batchId" element={<ListingDetail />} />}
          {['FARMER', 'BUYER', 'WAREHOUSE_OPERATOR'].includes(user.role) && <Route path="/orders" element={<OrdersPage />} />}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      )}
    </Routes>
    </Suspense>
  )
}
