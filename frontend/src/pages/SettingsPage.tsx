/**
 * Settings Page — Simulation controls, language, display preferences.
 */

import { useState, useEffect } from 'react'
import { Settings, Zap, Globe, Moon, Info, MapPin, Brain, RefreshCw } from 'lucide-react'
import { Scenario, Language, NetworkSnapshot } from '../types'
import { useScenario, useNetworks, useMlStatus } from '../hooks/useApi'
import { getScenarioLabel, cn } from '../utils'

interface SettingsPageProps {
  currentScenario: Scenario
  onScenarioChange: (s: Scenario) => void
  language: Language
  onLanguageChange: (l: Language) => void
  network?: NetworkSnapshot | null
}

// Kept in sync with backend.epanet.simulator.NETWORKS
const CITIES: { id: string; label: string; description: string }[] = [
  { id: 'douala',    label: 'Douala, Littoral Region',  description: '12 junctions · Coastal network fed by the Bassa & Japoma reservoirs.' },
  { id: 'bafoussam', label: 'Bafoussam, West Region',    description: '12 junctions · Highland-plateau network (~1500m) fed by the Mifi reservoir.' },
]

function buildScenarios(network?: NetworkSnapshot | null): { id: Scenario; description: string; risk: string }[] {
  const leakZone = network?.nodes.find(n => n.id === 'J7')?.name || 'J7'
  const upstreamZone = network?.nodes.find(n => n.id === 'J6')?.name || 'J6'
  return [
    { id: 'normal', description: 'All nodes operating at baseline pressure. No anomalies.', risk: 'None' },
    { id: 'small',  description: `Minor leak at ${leakZone} (J7). 1.5 L/s unaccounted flow.`, risk: 'Low' },
    { id: 'medium', description: `Significant leak at ${leakZone} (J7). 4.5 L/s loss. Pressure drop visible.`, risk: 'Medium' },
    { id: 'burst',  description: `Full pipe burst between ${upstreamZone}–${leakZone} (P7). Emergency situation.`, risk: 'Critical' },
  ]
}

const RISK_COLORS: Record<string, string> = {
  'None': 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10',
  'Low': 'text-amber-400 border-amber-500/30 bg-amber-500/10',
  'Medium': 'text-orange-400 border-orange-500/30 bg-orange-500/10',
  'Critical': 'text-red-400 border-red-500/30 bg-red-500/10',
}

export function SettingsPage({ currentScenario, onScenarioChange, language, onLanguageChange, network }: SettingsPageProps) {
  const { setScenario, loading } = useScenario()
  const { selectNetwork, loading: networkLoading } = useNetworks()
  const { status: mlStatus, fetchStatus, triggerRetrain, loading: mlLoading } = useMlStatus()
  const [simSpeed, setSimSpeed] = useState(2)

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, 15000)
    return () => clearInterval(interval)
  }, [fetchStatus])

  const handleScenario = async (s: Scenario) => {
    await setScenario(s)
    onScenarioChange(s)
  }

  const activeCity = network?.city || 'douala'
  const handleCity = async (id: string) => {
    if (id === activeCity) return
    await selectNetwork(id)
  }
  const SCENARIOS = buildScenarios(network)

  return (
    <div className="p-6 space-y-6 overflow-y-auto h-full max-w-3xl">

      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2.5 rounded-xl bg-white/[0.06] border border-white/[0.08]">
          <Settings className="text-white/60" size={20} />
        </div>
        <div>
          <h1 className="text-lg font-semibold text-white">Settings</h1>
          <p className="text-xs text-white/40">Simulation control and display preferences</p>
        </div>
      </div>

      {/* Network / City Selection */}
      <div className="glass-card p-5">
        <div className="flex items-center gap-2 mb-4">
          <MapPin size={16} className="text-cyan-400" />
          <h2 className="text-sm font-semibold text-white">Simulated Network</h2>
        </div>
        <p className="text-xs text-white/30 mb-3">
          Each municipality maps to a real, independently-editable EPANET .inp file under
          simulation/. Open it in EPANET Desktop and save — your edits reflect on this
          dashboard live, within one simulation tick.
        </p>
        <div className="space-y-3">
          {CITIES.map(({ id, label, description }) => (
            <button
              key={id}
              onClick={() => handleCity(id)}
              disabled={networkLoading}
              className={cn(
                'w-full text-left p-4 rounded-xl border transition-all duration-200',
                activeCity === id
                  ? 'border-cyan-500/40 bg-cyan-500/[0.08]'
                  : 'border-white/[0.08] hover:border-white/[0.15] hover:bg-white/[0.02]'
              )}
            >
              <div className="flex items-center gap-2 mb-1.5">
                {activeCity === id && <div className="w-2 h-2 rounded-full bg-cyan-400" />}
                <span className={cn(
                  'text-sm font-semibold',
                  activeCity === id ? 'text-cyan-400' : 'text-white/70'
                )}>
                  {label}
                </span>
              </div>
              <p className="text-xs text-white/40 ml-4">{description}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Scenario Control */}
      <div className="glass-card p-5">
        <div className="flex items-center gap-2 mb-4">
          <Zap size={16} className="text-cyan-400" />
          <h2 className="text-sm font-semibold text-white">Simulation Scenario</h2>
        </div>

        <div className="space-y-3">
          {SCENARIOS.map(({ id, description, risk }) => (
            <button
              key={id}
              onClick={() => handleScenario(id)}
              disabled={loading}
              className={cn(
                'w-full text-left p-4 rounded-xl border transition-all duration-200',
                currentScenario === id
                  ? 'border-cyan-500/40 bg-cyan-500/[0.08]'
                  : 'border-white/[0.08] hover:border-white/[0.15] hover:bg-white/[0.02]'
              )}
            >
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-2">
                  {currentScenario === id && (
                    <div className="w-2 h-2 rounded-full bg-cyan-400" />
                  )}
                  <span className={cn(
                    'text-sm font-semibold capitalize',
                    currentScenario === id ? 'text-cyan-400' : 'text-white/70'
                  )}>
                    {getScenarioLabel(id)}
                  </span>
                </div>
                <span className={cn('text-xs px-2 py-0.5 rounded-full border', RISK_COLORS[risk])}>
                  {risk} Risk
                </span>
              </div>
              <p className="text-xs text-white/40 ml-4">{description}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Language */}
      <div className="glass-card p-5">
        <div className="flex items-center gap-2 mb-4">
          <Globe size={16} className="text-blue-400" />
          <h2 className="text-sm font-semibold text-white">Report Language</h2>
        </div>
        <div className="grid grid-cols-2 gap-3">
          {([
            { code: 'en' as Language, label: 'English', flag: '🇬🇧', desc: 'AI reports in English' },
            { code: 'fr' as Language, label: 'Français', flag: '🇫🇷', desc: 'Rapports en français' },
          ]).map(({ code, label, flag, desc }) => (
            <button
              key={code}
              onClick={() => onLanguageChange(code)}
              className={cn(
                'p-4 rounded-xl border text-left transition-all duration-200',
                language === code
                  ? 'border-blue-500/40 bg-blue-500/[0.08]'
                  : 'border-white/[0.08] hover:border-white/[0.15]'
              )}
            >
              <div className="text-2xl mb-1">{flag}</div>
              <div className={cn('text-sm font-medium', language === code ? 'text-blue-400' : 'text-white/70')}>
                {label}
              </div>
              <div className="text-xs text-white/30 mt-0.5">{desc}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Simulation Speed */}
      <div className="glass-card p-5">
        <div className="flex items-center gap-2 mb-4">
          <Zap size={16} className="text-amber-400" />
          <h2 className="text-sm font-semibold text-white">Simulation Speed</h2>
        </div>
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs text-white/40">Update interval</span>
            <span className="text-xs font-mono text-white/70">{simSpeed}s</span>
          </div>
          <input
            type="range"
            min={1} max={10} step={1}
            value={simSpeed}
            onChange={(e) => setSimSpeed(Number(e.target.value))}
            className="w-full accent-cyan-400"
          />
          <div className="flex justify-between text-[10px] text-white/25">
            <span>1s (fast)</span>
            <span>5s (normal)</span>
            <span>10s (slow)</span>
          </div>
          <p className="text-xs text-white/30">
            Note: Actual backend interval is configured via SIMULATION_INTERVAL_SECONDS env var.
            This setting is for display purposes.
          </p>
        </div>
      </div>

      {/* ML Continuous Learning */}
      <div className="glass-card p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Brain size={16} className="text-violet-400" />
            <h2 className="text-sm font-semibold text-white">ML Continuous Learning</h2>
          </div>
          <button
            onClick={() => triggerRetrain()}
            disabled={mlLoading || mlStatus?.retraining}
            className="flex items-center gap-1.5 text-[11px] text-white/50 hover:text-violet-400 transition-colors disabled:opacity-40"
          >
            <RefreshCw size={12} className={mlStatus?.retraining ? 'animate-spin' : ''} />
            Retrain now
          </button>
        </div>
        <p className="text-xs text-white/30 mb-4">
          Models automatically learn from live simulation data and improve as more scenarios are observed.
        </p>
        <div className="grid grid-cols-2 gap-y-2 text-xs">
          {[
            { label: 'Status', value: mlStatus?.enabled ? (mlStatus.retraining ? 'Retraining…' : 'Active') : 'Disabled' },
            { label: 'Samples recorded', value: String(mlStatus?.total_recorded ?? '—') },
            { label: 'Training pool', value: String(mlStatus?.sample_counts?.combined ?? '—') },
            { label: 'Until next retrain', value: mlStatus ? `${mlStatus.samples_since_retrain}/${mlStatus.retrain_threshold}` : '—' },
            { label: 'Severity accuracy', value: mlStatus?.last_retrain_metrics?.severity_accuracy != null ? `${(mlStatus.last_retrain_metrics.severity_accuracy * 100).toFixed(1)}%` : '—' },
            { label: 'Last retrain', value: mlStatus?.last_retrain_at ? new Date(mlStatus.last_retrain_at).toLocaleString() : 'Pending' },
          ].map(({ label, value }) => (
            <div key={label} className="flex justify-between pr-4">
              <span className="text-white/30">{label}:</span>
              <span className="text-white/60 font-mono">{value}</span>
            </div>
          ))}
        </div>
      </div>

      {/* System Info */}
      <div className="glass-card p-5">
        <div className="flex items-center gap-2 mb-4">
          <Info size={16} className="text-white/40" />
          <h2 className="text-sm font-semibold text-white">System Information</h2>
        </div>
        <div className="grid grid-cols-2 gap-y-2 text-xs">
          {[
            { label: 'System', value: 'Maayan v1.0.0' },
            { label: 'Network', value: network?.city_label || 'Douala, Littoral Region' },
            { label: 'Nodes', value: `${network?.nodes.length ?? 12} junctions` },
            { label: 'Pipes', value: `${network?.pipes.length ?? 18} segments` },
            { label: 'Simulation', value: 'EPANET 2.2 / WNTR' },
            { label: 'ML Models', value: 'Continuous (IF + RF + GB)' },
            { label: 'LLM', value: 'Groq (Llama 3.3 70B)' },
          ].map(({ label, value }) => (
            <div key={label} className="flex justify-between pr-6">
              <span className="text-white/30">{label}:</span>
              <span className="text-white/60 font-mono">{value}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
