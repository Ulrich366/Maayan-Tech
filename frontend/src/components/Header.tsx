import { motion } from 'framer-motion'
import { Bell, RefreshCw, Cpu, FlaskConical, MapPin } from 'lucide-react'
import { ConnectionBadge } from './ui/ConnectionBadge'
import { useScenario, useNetworks } from '../hooks/useApi'
import { Scenario } from '../types'
import { getScenarioLabel, cn } from '../utils'
import { formatTime } from '../utils'

interface HeaderProps {
  title: string
  isConnected: boolean
  connectionAttempt: number
  scenario: Scenario
  onScenarioChange?: (s: Scenario) => void
  lastUpdate: Date | null
  leakCount?: number
  engine?: 'epanet' | 'synthetic'
  city?: string
  onCityChange?: (city: string) => void
}

const SCENARIOS: Scenario[] = ['normal', 'small', 'medium', 'burst']

// Kept in sync with backend.epanet.simulator.NETWORKS
const CITIES: { id: string; label: string }[] = [
  { id: 'douala', label: 'Douala' },
  { id: 'bafoussam', label: 'Bafoussam' },
]

const SCENARIO_COLORS: Record<Scenario, string> = {
  normal: 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10',
  small:  'text-amber-400 border-amber-500/30 bg-amber-500/10',
  medium: 'text-orange-400 border-orange-500/30 bg-orange-500/10',
  burst:  'text-red-400 border-red-500/30 bg-red-500/10',
}

export function Header({
  title, isConnected, connectionAttempt, scenario,
  onScenarioChange, lastUpdate, leakCount = 0, engine, city, onCityChange
}: HeaderProps) {
  const { setScenario, loading } = useScenario()
  const { selectNetwork, loading: networkLoading } = useNetworks()

  const handleScenarioChange = async (s: Scenario) => {
    await setScenario(s)
    onScenarioChange?.(s)
  }

  const handleCityChange = async (id: string) => {
    if (id === city) return
    await selectNetwork(id)
    onCityChange?.(id)
  }

  return (
    <header className="flex flex-wrap items-center justify-between gap-3 px-6 py-4 border-b border-white/[0.06] bg-[#060f21]/80 backdrop-blur-sm">
      <div>
        <h1 className="text-lg font-semibold text-white">{title}</h1>
        {lastUpdate && (
          <p className="text-xs text-white/30 mt-0.5">
            Last updated: {formatTime(lastUpdate)}
          </p>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        {/* Data engine indicator — always visible so it's clear whether data is real EPANET output or fallback */}
        {engine && (
          <div className={cn(
            'flex items-center gap-1.5 px-2.5 py-1.5 rounded-full text-xs font-medium border',
            engine === 'epanet'
              ? 'bg-cyan-500/10 border-cyan-500/30 text-cyan-400'
              : 'bg-amber-500/10 border-amber-500/30 text-amber-400'
          )}>
            {engine === 'epanet' ? <Cpu size={12} /> : <FlaskConical size={12} />}
            {engine === 'epanet' ? 'Real EPANET 2.2' : 'Synthetic Fallback'}
          </div>
        )}

        {/* City / network selector — switch which simulated EPANET network drives the dashboard */}
        {city && (
          <div className="flex items-center gap-1 bg-white/[0.04] rounded-lg p-1 border border-white/[0.08]">
            <MapPin size={12} className="text-white/30 ml-1.5" />
            {CITIES.map((c) => (
              <button
                key={c.id}
                onClick={() => handleCityChange(c.id)}
                disabled={networkLoading}
                className={cn(
                  'px-2.5 py-1.5 rounded-md text-xs font-medium transition-all duration-200 border',
                  city === c.id
                    ? 'text-cyan-400 border-cyan-500/30 bg-cyan-500/10'
                    : 'text-white/40 border-transparent hover:text-white/70 hover:bg-white/[0.05]'
                )}
              >
                {c.label}
              </button>
            ))}
          </div>
        )}

        {/* Scenario selector */}
        <div className="flex items-center gap-1 bg-white/[0.04] rounded-lg p-1 border border-white/[0.08]">
          {SCENARIOS.map((s) => (
            <button
              key={s}
              onClick={() => handleScenarioChange(s)}
              disabled={loading}
              className={cn(
                'px-3 py-1.5 rounded-md text-xs font-medium transition-all duration-200 capitalize border',
                scenario === s
                  ? SCENARIO_COLORS[s]
                  : 'text-white/40 border-transparent hover:text-white/70 hover:bg-white/[0.05]'
              )}
            >
              {loading && scenario === s ? (
                <RefreshCw className="w-3 h-3 animate-spin" />
              ) : (
                s
              )}
            </button>
          ))}
        </div>

        {/* Alert badge */}
        {leakCount > 0 && (
          <motion.div
            animate={{ scale: [1, 1.05, 1] }}
            transition={{ duration: 1.5, repeat: Infinity }}
            className="relative"
          >
            <button className="p-2 rounded-lg bg-red-500/15 border border-red-500/30 text-red-400">
              <Bell size={16} />
            </button>
            <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 rounded-full text-[10px] font-bold text-white flex items-center justify-center">
              {leakCount}
            </span>
          </motion.div>
        )}

        {/* Connection status */}
        <ConnectionBadge isConnected={isConnected} attempt={connectionAttempt} />
      </div>
    </header>
  )
}
