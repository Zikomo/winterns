import { Routes, Route } from 'react-router-dom'
import { HomePage, HealthPage, LoginPage, RegisterPage, AuthCallbackPage } from '@/pages'
import { ProtectedRoute } from '@/components/ProtectedRoute'

function App() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/" element={<HomePage />} />
      <Route path="/health" element={<HealthPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/auth/callback" element={<AuthCallbackPage />} />

      {/* Protected routes */}
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <DashboardPlaceholder />
          </ProtectedRoute>
        }
      />
    </Routes>
  )
}

// Temporary placeholder until Dashboard is implemented in #18
function DashboardPlaceholder() {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="text-center">
        <h1 className="text-2xl font-semibold text-gray-900 mb-2">Dashboard</h1>
        <p className="text-gray-600">Coming soon in issue #18</p>
      </div>
    </div>
  )
}

export default App
