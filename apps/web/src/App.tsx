import { Routes, Route } from 'react-router-dom'
import { HomePage, HealthPage } from '@/pages'

function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/health" element={<HealthPage />} />
    </Routes>
  )
}

export default App
