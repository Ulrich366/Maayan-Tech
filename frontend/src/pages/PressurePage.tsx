/**
 * Pressure Page — Live charts for pressure, flow, and leak probability.
 */

import { useState, useEffect, useRef } from 'react'
import {
  LineChart, Line, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, ReferenceLine,
  BarChart, Bar
} from 'recharts'
import { NetworkSnapshot, LeakReport } from '../types'
import { cn } from '../utils'

interface PressurePageProps {
  network: NetworkSnapshot | null
  leakReport: LeakReport | null
}

const NODE_COLORS = [
  '#22d3ee', '#60a5fa', '#a78bfa', '#34d399',
  '#fbbf24', '#f87171', '#fb923c', '#e879f9',
  '#4ade80', '#38bdf8', '#f472b6', '#a3e635',
]

const MAX_POINTS = 80

type ChartPoint = { time: string; [key: string]: string | number }

export function PressurePage({ network, leakReport }: PressurePageProps) {
  const [history, setHistory] = useState<ChartPoint[]>([])
  const [probHistory, setProbHistory] = useState<{ time: string; probability: number; confidence: number }[]>([])
  const [activeNodes, setActiveNodes] = useState<string[]>(['J1', 'J6', 'J7', 'J8'])
  const tickRef = useRef(0)

  useEffect(() => {
    if (!network) return
    tickRef.current++
    const time = new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })

    const point: ChartPoint = { time }
    network.nodes.forEach(n => { point[n.id] = n.pressure })
    setHistory(prev => [...prev.slice(-MAX_POINTS), point])

    if (leakReport) {
      setProbHistory(prev => [...prev.slice(-MAX_POINTS), {
        time,
        probability: leakReport.probability,
        confidence: leakReport.confidence,
      }])
    }
  }, [network, leakReport])

  const nodeIds = network?.nodes.map(n => n.id) ?? []

  return (
    <div className="p-6 space-y-6 overflow-y-auto h-full">

      {/* Node selector */}
      <div className="glass-card p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-white">Pressure Monitor</h2>
          <span className="text-xs text-white/40">Select nodes to display</span>
        </div>
        <div className="flex flex-wrap gap-2">
          {nodeIds.map((id, i) => (
            <button
              key={id}
              onClick={() => setActiveNodes(prev =>
                prev.includes(id) ? prev.filter(n => n !== id) : [...prev, id]
              )}
              className={cn(
                'px-3 py-1 rounded-full text-xs font-medium border transition-all duration-200',
                activeNodes.includes(id)
                  ? 'border-current text-white'
                  : 'border-white/10 text-white/30 hover:border-white/30'
              )}
              style={activeNodes.includes(id) ? {
                backgroundColor: `${NODE_COLORS[i % NODE_COLORS.length]}20`,
                borderColor: NODE_COLORS[i % NODE_COLORS.length],
                color: NODE_COLORS[i % NODE_COLORS.length],
              } : {}}
            >
              {id}
            </button>
          ))}
        </div>
      </div>

      {/* Pressure vs Time — Multi-line */}
      <div className="glass-card p-4">
        <h2 className="text-sm font-semibold text-white mb-1">Pressure vs Time (bar)</h2>
        <p className="text-xs text-white/40 mb-4">Real-time pressure readings at selected nodes</p>
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={history} margin={{ top: 5, right: 10, bottom: 5, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
            <XAxis dataKey="time" tick={{ fill: 'rgba(255,255,255,0.25)', fontSize: 10 }} interval="preserveStartEnd" />
            <YAxis tick={{ fill: 'rgba(255,255,255,0.25)', fontSize: 10 }} domain={['auto', 'auto']} />
            <Tooltip
              contentStyle={{ background: '#0a1628', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', fontSize: '11px' }}
              labelStyle={{ color: 'rgba(255,255,255,0.6)' }}
            />
            <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '12px' }} />
            {activeNodes.map((id, i) => (
              <Line
                key={id}
                type="monotone"
                dataKey={id}
                stroke={NODE_COLORS[nodeIds.indexOf(id) % NODE_COLORS.length]}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4 }}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Leak Probability over time */}
      <div className="glass-card p-4">
        <h2 className="text-sm font-semibold text-white mb-1">Leak Probability (%)</h2>
        <p className="text-xs text-white/40 mb-4">Combined ML + statistical detection confidence</p>
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={probHistory} margin={{ top: 5, right: 10, bottom: 5, left: 0 }}>
            <defs>
              <linearGradient id="probGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#ef4444" stopOpacity={0.25} />
                <stop offset="95%" stopColor="#ef4444" stopOpacity={0.02} />
              </linearGradient>
              <linearGradient id="confGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#60a5fa" stopOpacity={0.15} />
                <stop offset="95%" stopColor="#60a5fa" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
            <XAxis dataKey="time" tick={{ fill: 'rgba(255,255,255,0.25)', fontSize: 10 }} interval="preserveStartEnd" />
            <YAxis tick={{ fill: 'rgba(255,255,255,0.25)', fontSize: 10 }} domain={[0, 100]} />
            <Tooltip
              contentStyle={{ background: '#0a1628', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', fontSize: '11px' }}
              labelStyle={{ color: 'rgba(255,255,255,0.6)' }}
            />
            <ReferenceLine y={80} stroke="#ef4444" strokeDasharray="4 4" strokeOpacity={0.5}
              label={{ value: 'Alert threshold (80%)', fill: '#ef4444', fontSize: 10 }} />
            <Area type="monotone" dataKey="probability" stroke="#ef4444" fill="url(#probGrad)" strokeWidth={2} dot={false} isAnimationActive={false} name="Probability" />
            <Area type="monotone" dataKey="confidence" stroke="#60a5fa" fill="url(#confGrad)" strokeWidth={1.5} strokeDasharray="4 3" dot={false} isAnimationActive={false} name="ML Confidence" />
            <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }} />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Current pressure bar chart */}
      <div className="glass-card p-4">
        <h2 className="text-sm font-semibold text-white mb-1">Current Pressure by Node</h2>
        <p className="text-xs text-white/40 mb-4">Live snapshot — baseline vs current</p>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart
            data={network?.nodes.map(n => ({
              name: n.id,
              current: n.pressure,
              baseline: n.pressure_baseline,
            })) ?? []}
            margin={{ top: 5, right: 10, bottom: 5, left: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
            <XAxis dataKey="name" tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 10 }} />
            <YAxis tick={{ fill: 'rgba(255,255,255,0.25)', fontSize: 10 }} domain={['auto', 'auto']} />
            <Tooltip
              contentStyle={{ background: '#0a1628', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', fontSize: '11px' }}
              labelStyle={{ color: 'rgba(255,255,255,0.6)' }}
            />
            <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }} />
            <Bar dataKey="baseline" name="Baseline" fill="rgba(255,255,255,0.08)" radius={[2, 2, 0, 0]} />
            <Bar dataKey="current" name="Current" fill="#22d3ee" fillOpacity={0.7} radius={[2, 2, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
