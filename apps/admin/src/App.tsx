import { Routes, Route, Link, useNavigate } from 'react-router-dom'
import { useEffect } from 'react'
import AdminRegisterPage from './pages/AdminRegisterPage'
import AdminLoginPage from './pages/AdminLoginPage'
import ProtectedRoute from './components/ProtectedRoute'
import { useAdminStore } from './lib/store'
import AdminLayout from './components/layout/AdminLayout'
import Dashboard from './pages/Dashboard'
import Residents from './pages/Residents'
import Benefits from './pages/Benefits'
import Requests from './pages/Requests'
import Marketplace from './pages/Marketplace'
import Admins from './pages/Admins'
import Reports from './pages/Reports'
import Profile from './pages/Profile'
import Announcements from './pages/Announcements'
import Issues from './pages/Issues'
import TransactionsPage from './pages/Transactions'
import VerifyTicket from './pages/VerifyTicket'

export default function App() {
  const isAuthenticated = useAdminStore((s) => s.isAuthenticated)
  const navigate = useNavigate()

  // Prevent accessing private routes after logout via back button/history cache
  useEffect(() => {
    const recheckAuth = () => {
      const { isAuthenticated: auth, user } = useAdminStore.getState()
      if (!auth || !user) {
        navigate('/login', { replace: true })
      }
    }

    window.addEventListener('pageshow', recheckAuth)
    window.addEventListener('popstate', recheckAuth)
    return () => {
      window.removeEventListener('pageshow', recheckAuth)
      window.removeEventListener('popstate', recheckAuth)
    }
  }, [navigate])

  return (
    <div className="min-h-screen bg-gradient-to-b from-ocean-50 to-white">
      <Routes>
        {/* Admin routes (modern layout) */}
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <AdminLayout>
                <Dashboard />
              </AdminLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/residents"
          element={
            <ProtectedRoute>
              <AdminLayout>
                <Residents />
              </AdminLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/benefits"
          element={
            <ProtectedRoute>
              <AdminLayout>
                <Benefits />
              </AdminLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/requests"
          element={
            <ProtectedRoute>
              <AdminLayout>
                <Requests />
              </AdminLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/verify-ticket"
          element={
            <ProtectedRoute>
              <AdminLayout>
                <VerifyTicket />
              </AdminLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/marketplace"
          element={
            <ProtectedRoute>
              <AdminLayout>
                <Marketplace />
              </AdminLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/transactions"
          element={
            <ProtectedRoute>
              <AdminLayout>
                <TransactionsPage />
              </AdminLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/issues"
          element={
            <ProtectedRoute>
              <AdminLayout>
                <Issues />
              </AdminLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/admins"
          element={
            <ProtectedRoute>
              <AdminLayout>
                <Admins />
              </AdminLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/profile"
          element={
            <ProtectedRoute>
              <AdminLayout>
                <Profile />
              </AdminLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/announcements"
          element={
            <ProtectedRoute>
              <AdminLayout>
                <Announcements />
              </AdminLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/reports"
          element={
            <ProtectedRoute>
              <AdminLayout>
                <Reports />
              </AdminLayout>
            </ProtectedRoute>
          }
        />

        {/* Auth pages - With nav */}
        <Route
          path="/*"
          element={
            <>
              {!isAuthenticated && (
                <nav className="sticky top-0 z-10 border-b bg-white/70 backdrop-blur-xl">
                  <div className="container mx-auto px-4 py-3 flex items-center justify-between">
                    <Link to="/" className="font-serif font-semibold text-gray-900">MunLink Admin</Link>
                    <div className="flex items-center gap-6">
                      <Link to="/login" className="hover:text-ocean-700">Login</Link>
                      <Link to="/register" className="hover:text-ocean-700">Create Admin</Link>
                    </div>
                  </div>
                </nav>
              )}
              <main className="container mx-auto px-4 py-10">
                <Routes>
                  <Route path="/" element={<AdminLoginPage />} />
                  <Route path="/login" element={<AdminLoginPage />} />
                  <Route path="/register" element={<AdminRegisterPage />} />
                </Routes>
              </main>
            </>
          }
        />
      </Routes>
    </div>
  )
}


