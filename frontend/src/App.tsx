import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import HomePage from './app/page'
import PapersPage from './app/papers/page'
import PaperDetailPage from './app/papers/[id]/page'
import RecommendationsPage from './app/recommendations/page'
import ReportsPage from './app/reports/page'
import InterestsPage from './app/interests/page'
import SettingsPage from './app/settings/page'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<HomePage />} />
        <Route path="papers" element={<PapersPage />} />
        <Route path="papers/:id" element={<PaperDetailPage />} />
        <Route path="recommendations" element={<RecommendationsPage />} />
        <Route path="reports" element={<ReportsPage />} />
        <Route path="reports/:id" element={<ReportsPage />} />
        <Route path="interests" element={<InterestsPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  )
}

export default App
