import { useState, useCallback } from 'react'
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { Sidebar } from './components/Sidebar'
import { Header } from './components/Header'
import { DashboardPage } from './pages/DashboardPage'
import { NetworkPage } from './pages/NetworkPage'
import { PressurePage } from './pages/PressurePage'
import { ReportPage } from './pages/ReportPage'
import { HistoryPage } from './pages/HistoryPage'
import { IoTPage } from './pages/IoTPage'
import { SettingsPage } from './pages/SettingsPage'
import { useWebSocket } from './hooks/useWebSocket'
import { Scenario, Language } from './types'

const PAGE_TITLES: Record<string, string> = {
  '/':         'Command Center',
  '/network':  'Live Network',
  '/pressure': 'Pressure Analytics',
  '/report':   'AI Report',
  '/history':  'Event History',
  '/iot':      'IoT Sensor Nodes',
  '/settings': 'Settings',
}

function AppContent() {
  const location = useLocation()
  const { isConnected, network, leakReport, lastTick, sendMessage, connectionAttempt } = useWebSocket()

  const [scenario, setScenario] = useState<Scenario>('normal')
  const [language, setLanguage] = useState<Language>('en')
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null)

  // Track last update time
  if (network && (!lastUpdate || lastTick > 0)) {
    // Use ref-less update (called from render — safe because lastTick changes trigger re-render)
  }

  const handleScenarioChange = useCallback((s: Scenario) => {
    setScenario(s)
    sendMessage({ type: 'set_scenario', scenario: s })
  }, [sendMessage])

  const leakCount = leakReport?.detected ? 1 : 0
  const title = PAGE_TITLES[location.pathname] || 'Maayan'

  return (
    <div className="flex h-screen overflow-hidden bg-[#040d1a]">
      <Sidebar />

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <Header
          title={title}
          isConnected={isConnected}
          connectionAttempt={connectionAttempt}
          scenario={scenario}
          onScenarioChange={handleScenarioChange}
          lastUpdate={network ? new Date() : null}
          leakCount={leakCount}
          engine={network?.engine}
          city={network?.city}
        />

        <main className="flex-1 overflow-hidden">
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.2 }}
              className="h-full"
            >
              <Routes location={location}>
                <Route path="/" element={
                  <DashboardPage network={network} leakReport={leakReport} />
                } />
                <Route path="/network" element={
                  <NetworkPage network={network} leakReport={leakReport} />
                } />
                <Route path="/pressure" element={
                  <PressurePage network={network} leakReport={leakReport} />
                } />
                <Route path="/report" element={
                  <ReportPage leakReport={leakReport} />
                } />
                <Route path="/history" element={
                  <HistoryPage />
                } />
                <Route path="/iot" element={
                  <IoTPage />
                } />
                <Route path="/settings" element={
                  <SettingsPage
                    currentScenario={scenario}
                    onScenarioChange={handleScenarioChange}
                    language={language}
                    onLanguageChange={setLanguage}
                    network={network}
                  />
                } />
              </Routes>
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  )
}
