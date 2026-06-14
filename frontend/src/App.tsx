import { Routes, Route } from 'react-router-dom'
import Layout from './layouts/Layout'
import ErrorBoundary from './components/ErrorBoundary'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import JurisdictionListPage from './pages/JurisdictionListPage'
import NewFilingPage from './pages/NewFilingPage'
import FilingDetailPage from './pages/FilingDetailPage'
import SettingsPage from './pages/SettingsPage'
import AgentChatPage from './pages/AgentChatPage'
import CasePreviewPage from './pages/CasePreviewPage'
import CapabilityMatrixPage from './pages/CapabilityMatrixPage'
import ImportHubPage from './pages/ImportHubPage'
import ImportPreviewPage from './pages/ImportPreviewPage'

/**
 * 路由层错误边界策略：
 *   - 外层 <ErrorBoundary scope="App">：整树兜底，防止任何页面崩溃导致白屏
 *   - 每个 Route element 单独包一层 <ErrorBoundary scope="页面名">：
 *     单页崩溃只影响该页（侧栏/顶栏保留），用户可关闭弹窗继续浏览其他页
 */
function App() {
  return (
    <ErrorBoundary scope="App">
      <Routes>
        <Route
          path="/login"
          element={
            <ErrorBoundary scope="LoginPage">
              <LoginPage />
            </ErrorBoundary>
          }
        />
        <Route element={<Layout />}>
          <Route
            path="/"
            element={
              <ErrorBoundary scope="DashboardPage">
                <DashboardPage />
              </ErrorBoundary>
            }
          />
          <Route
            path="/dashboard"
            element={
              <ErrorBoundary scope="DashboardPage">
                <DashboardPage />
              </ErrorBoundary>
            }
          />
          <Route
            path="/jurisdictions"
            element={
              <ErrorBoundary scope="JurisdictionListPage">
                <JurisdictionListPage />
              </ErrorBoundary>
            }
          />
          <Route
            path="/cases/:presetId"
            element={
              <ErrorBoundary scope="CasePreviewPage">
                <CasePreviewPage />
              </ErrorBoundary>
            }
          />
          <Route
            path="/docs/jiahang-capability-matrix"
            element={
              <ErrorBoundary scope="CapabilityMatrixPage">
                <CapabilityMatrixPage />
              </ErrorBoundary>
            }
          />
          <Route
            path="/filings/new"
            element={
              <ErrorBoundary scope="NewFilingPage">
                <NewFilingPage />
              </ErrorBoundary>
            }
          />
          <Route
            path="/filings/:id"
            element={
              <ErrorBoundary scope="FilingDetailPage">
                <FilingDetailPage />
              </ErrorBoundary>
            }
          />
          <Route
            path="/agent"
            element={
              <ErrorBoundary scope="AgentChatPage">
                <AgentChatPage />
              </ErrorBoundary>
            }
          />
          <Route
            path="/settings"
            element={
              <ErrorBoundary scope="SettingsPage">
                <SettingsPage />
              </ErrorBoundary>
            }
          />
          <Route
            path="/import"
            element={
              <ErrorBoundary scope="ImportHubPage">
                <ImportHubPage />
              </ErrorBoundary>
            }
          />
          <Route
            path="/import/preview"
            element={
              <ErrorBoundary scope="ImportPreviewPage">
                <ImportPreviewPage />
              </ErrorBoundary>
            }
          />
        </Route>
      </Routes>
    </ErrorBoundary>
  )
}

export default App
