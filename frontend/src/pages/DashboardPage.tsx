/**
 * Dashboard Page — Main command center view.
 * Shows KPI metrics, live alerts, network summary, and pressure overview.
 */

import { useMemo, useRef, useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import {
  Droplets, AlertTriangle, Activity, Gauge,
  Server, CheckCircle, TrendingDown, Zap
} from 'lucide-react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine
} from 'recharts'
import { NetworkSnapshot, LeakReport } from '../types'
import { MetricCard } from '../components/ui/MetricCard'
import { LeakAlert } from '../components/LeakAlert'
import { StatusIndicator } from '../components/ui/StatusIndicator'
import {
  getHealthColor, formatPressure, formatFlow,
  getScenarioLabel, cn
} from '../utils'

interface DashboardPageProps {
  network: NetworkSnapshot | null
  leakReport: LeakReport | null
}

const MAX_HISTORY = 60

export function DashboardPage({ network, leakReport }: DashboardPageProps) {
  const [pressureHistory, setPressureHistory] = useState<{ time: string; avg: number; min: number; max: number }[]>([])
  const tickRef = useRef(0)

  // Build rolling pressure history
  useEffect(() => {
    if (!network) return
    tickRef.current++

    const pressures = network.nodes.map(n => n.pressure)
    const avg = pressures.reduce((a, b) => a + b, 0) / pressures.length
    const min = Math.min(...pressures)
    const max = Math.max(...pressures)
    const time = new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })

    setPressureHistory(prev => {
      const next = [...prev, { time, avg: +avg.toFixed(3), min: +min.toFixed(3), max: +max.toFixed(3) }]
      return next.slice(-MAX_HISTORY)
    })
  }, [network])

  const stats = useMemo(() => {
    if (!network) return null
    const nodes = network.nodes
    const healthy = nodes.filter(n => n.status === 'normal').length
    const leaking = nodes.filter(n => n.status === 'leak' || n.status === 'burst').length
    const warning = nodes.filter(n => n.status === 'warning').length
    const avgPressure = nodes.reduce((s, n) => s + n.pressure, 0) / nodes.length
    return { healthy, leaking, warning, avgPressure, total: nodes.length }
  }, [network])

  if (!network) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center text-white/30">
          <div className="w-12 h-12 border-2 border-cyan-500/30 border-t-cyan-400 rounded-full animate-spin mx-auto mb-4" />
          <p className="text-sm">Connecting to Maayan...</p>
        </div>
      </div>
    )
  }

  const healthColor = getHealthColor(network.system_health)

  return (
    <div className="p-6 space-y-6 overflow-y-auto h-full">

      {/* Leak Alert Banner */}
      {leakReport && <LeakAlert report={leakReport} />}

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="System Health"
          value={`${network.system_health.toFixed(1)}`}
          unit="%"
          icon={<Activity size={16} />}
          color={healthColor}
          subtitle={getScenarioLabel(network.scenario)}
        />
        <MetricCard
          title="Healthy Nodes"
          value={stats?.healthy ?? 0}
          unit={`/ ${stats?.total ?? 0}`}
          icon={<CheckCircle size={16} />}
          color="#10b981"
          subtitle="Operating normally"
        />
        <MetricCard
          title="Active Leaks"
          value={stats?.leaking ?? 0}
          icon={<AlertTriangle size={16} />}
          color={(stats?.leaking ?? 0) > 0 ? '#ef4444' : '#10b981'}
          alert={(stats?.leaking ?? 0) > 0}
          subtitle={(stats?.leaking ?? 0) > 0 ? 'Requires attention' : 'Network secure'}
        />
        <MetricCard
          title="Water Loss"
          value={formatFlow(network.total_leakage).split(' ')[0]}
          unit="L/s"
          icon={<Droplets size={16} />}
          color={network.total_leakage > 0 ? '#f97316' : '#10b981'}
          subtitle={network.total_leakage > 0 ? 'Unaccounted loss' : 'No leakage'}
          trend={network.total_leakage > 0 ? 'up' : 'stable'}
        />
        <MetricCard
          title="Avg Pressure"
          value={stats ? stats.avgPressure.toFixed(2) : '—'}
          unit="bar"
          icon={<Gauge size={16} />}
          color="#22d3ee"
          subtitle="Network average"
        />
        <MetricCard
          title="Total Demand"
          value={network.total_demand.toFixed(1)}
          unit="L/s"
          icon={<Server size={16} />}
          color="#60a5fa"
          subtitle="Consumer demand"
        />
        <MetricCard
          title="Warning Nodes"
          value={stats?.warning ?? 0}
          icon={<Zap size={16} />}
          color="#f59e0b"
          subtitle="Pressure anomaly"
        />
        <MetricCard
          title="Leak Probability"
          value={leakReport ? `${leakReport.probability.toFixed(0)}` : '0'}
          unit="%"
          icon={<TrendingDown size={16} />}
          color={leakReport?.detected ? '#ef4444' : '#10b981'}
          subtitle="ML + Statistical"
        />
      </div>

      {/* Pressure History Chart + Node Status */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

        {/* Area Chart */}
        <div className="lg:col-span-2 glass-card p-4">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-semibold text-white">Pressure History</h2>
              <p className="text-xs text-white/40 mt-0.5">Network-wide average (bar)</p>
            </div>
            <div className="flex items-center gap-3 text-xs">
              <span className="flex items-center gap-1.5"><span className="w-3 h-0.5 bg-cyan-400 inline-block" /> Avg</span>
              <span className="flex items-center gap-1.5 text-white/40"><span className="w-3 h-0.5 bg-blue-400/40 inline-block" /> Range</span>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={pressureHistory} margin={{ top: 5, right: 5, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="pressureGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#22d3ee" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#22d3ee" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="rangeGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.1} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
              <XAxis dataKey="time" tick={{ fill: 'rgba(255,255,255,0.25)', fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tick={{ fill: 'rgba(255,255,255,0.25)', fontSize: 10 }} domain={['auto', 'auto']} />
              <Tooltip
                contentStyle={{ background: '#0a1628', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', fontSize: '12px' }}
                labelStyle={{ color: 'rgba(255,255,255,0.6)' }}
                itemStyle={{ color: '#22d3ee' }}
              />
              {leakReport?.detected && (
                <ReferenceLine y={leakReport.pressure_drop > 0 ? Math.min(...pressureHistory.map(d => d.min)) : undefined}
                  stroke="#ef4444" strokeDasharray="3 3" label={{ value: 'Anomaly', fill: '#ef4444', fontSize: 10 }} />
              )}
              <Area type="monotone" dataKey="max" stroke="#3b82f6" strokeWidth={0} fill="url(#rangeGrad)" />
              <Area type="monotone" dataKey="min" stroke="#3b82f6" strokeWidth={0} fill="transparent" />
              <Area type="monotone" dataKey="avg" stroke="#22d3ee" strokeWidth={2} fill="url(#pressureGrad)" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Node Status Grid */}
        <div className="glass-card p-4">
          <h2 className="text-sm font-semibold text-white mb-3">Node Status</h2>
          <div className="space-y-1.5 overflow-y-auto max-h-[240px]">
            {network.nodes.map((node) => (
              <motion.div
                key={node.id}
                layout
                className={cn(
                  'flex items-center justify-between px-3 py-2 rounded-lg border',
                  node.status === 'normal'  && 'border-transparent bg-white/[0.02]',
                  node.status === 'warning' && 'border-amber-500/20 bg-amber-500/[0.04]',
                  node.status === 'leak'    && 'border-red-500/30 bg-red-500/[0.06]',
                  node.status === 'burst'   && 'border-red-600/40 bg-red-600/[0.08]',
                )}
              >
                <div className="flex items-center gap-2">
                  <StatusIndicator status={node.status} size="sm" />
                  <div>
                    <div className="text-xs font-medium text-white/80">{node.id}</div>
                    <div className="text-[10px] text-white/30">{node.name}</div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-xs font-mono text-white/70">{node.pressure.toFixed(2)} bar</div>
                  {node.pressure_drop > 0.1 && (
                    <div className="text-[10px] text-red-400 font-mono">-{node.pressure_drop.toFixed(2)}</div>
                  )}
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </div>

      {/* Leak Details */}
      {leakReport?.detected && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          className="glass-card p-4 border border-red-500/20"
        >
          <h2 className="text-sm font-semibold text-red-400 mb-3 flex items-center gap-2">
            <AlertTriangle size={14} />
            Leak Analysis Details
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <div className="text-xs text-white/40 mb-1">Location</div>
              <div className="text-white/80 font-medium">{leakReport.location}</div>
            </div>
            <div>
              <div className="text-xs text-white/40 mb-1">Detection Method</div>
              <div className="text-white/80 font-medium capitalize">{leakReport.detection_method}</div>
            </div>
            <div>
              <div className="text-xs text-white/40 mb-1">Affected Zones</div>
              <div className="text-white/80 font-medium">
                {leakReport.affected_nodes.join(', ') || 'None'}
              </div>
            </div>
            <div>
              <div className="text-xs text-white/40 mb-1">Alert Level</div>
              <div className={cn('font-bold capitalize',
                leakReport.alert_level === 'red' ? 'text-red-400' :
                leakReport.alert_level === 'orange' ? 'text-orange-400' :
                leakReport.alert_level === 'yellow' ? 'text-amber-400' : 'text-emerald-400'
              )}>
                {leakReport.alert_level.toUpperCase()}
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </div>
  )
}
