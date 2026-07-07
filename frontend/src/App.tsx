import { Route, Routes } from 'react-router-dom'
import AppShell from './layout/AppShell'
import DispatchPage from './pages/DispatchPage'
import BookAnalyticsPage from './pages/BookAnalyticsPage'
import ClientsPage from './pages/ClientsPage'
import ClientProfilePage from './pages/ClientProfilePage'
import SegmentsPage from './pages/SegmentsPage'
import MarketPage from './pages/MarketPage'
import CampaignsPage from './pages/CampaignsPage'
import AgentActivityPage from './pages/AgentActivityPage'
import AssistantPage from './pages/AssistantPage'
import EvalPage from './pages/EvalPage'
import './App.css'

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<DispatchPage />} />
        <Route path="book" element={<BookAnalyticsPage />} />
        <Route path="clients" element={<ClientsPage />} />
        <Route path="clients/:clientId" element={<ClientProfilePage />} />
        <Route path="segments" element={<SegmentsPage />} />
        <Route path="market" element={<MarketPage />} />
        <Route path="campaigns" element={<CampaignsPage />} />
        <Route path="assistant" element={<AssistantPage />} />
        <Route path="agent" element={<AgentActivityPage />} />
        <Route path="eval" element={<EvalPage />} />
      </Route>
    </Routes>
  )
}
