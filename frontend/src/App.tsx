import { Routes, Route } from 'react-router-dom'
import Layout from './layouts/Layout'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import JurisdictionListPage from './pages/JurisdictionListPage'
import NewFilingPage from './pages/NewFilingPage'
import FilingDetailPage from './pages/FilingDetailPage'
import SettingsPage from './pages/SettingsPage'
import AgentChatPage from './pages/AgentChatPage'
import CasePreviewPage from './pages/CasePreviewPage'

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<Layout />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/jurisdictions" element={<JurisdictionListPage />} />
        <Route path="/cases/:presetId" element={<CasePreviewPage />} />
        <Route path="/filings/new" element={<NewFilingPage />} />
        <Route path="/filings/:id" element={<FilingDetailPage />} />
        <Route path="/agent" element={<AgentChatPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  )
}

export default App
