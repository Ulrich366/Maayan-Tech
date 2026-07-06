/**
 * Network Page — Full-screen digital twin network visualization.
 */

import { useState } from 'react'
import { motion } from 'framer-motion'
import { NetworkDiagram } from '../components/NetworkDiagram'
import { StatusIndicator } from '../components/ui/StatusIndicator'
import { NetworkSnapshot, NodeState, LeakReport } from '../types'
import { formatPressure, formatFlow, getNodeStatusBg, cn } from '../utils'

interface NetworkPageProps {
  network: NetworkSnapshot | null
  leakReport: LeakReport | null
}

export function NetworkPage({ network, leakReport }: NetworkPageProps) {
  const [selectedNode, setSelectedNode] = useState<NodeState | null>(null)

  return (
    <div className="flex h-full overflow-hidden">

      {/* Network diagram — main area */}
      <div className="flex-1 relative bg-[#040d1a]">
        <NetworkDiagram
          network={network}
          onNodeClick={setSelectedNode}
        />

        {/* Overlay stats */}
        {network && (
          <div className="absolute top-4 left-4 flex gap-2">
            {[
              { label: 'Normal',  count: network.nodes.filter(n => n.status === 'normal').length,  color: '#10b981' },
              { label: 'Warning', count: network.nodes.filter(n => n.status === 'warning').length, color: '#f59e0b' },
              { label: 'Leak',    count: network.nodes.filter(n => n.status === 'leak').length,    color: '#ef4444' },
              { label: 'Burst',   count: network.nodes.filter(n => n.status === 'burst').length,   color: '#dc2626' },
            ].map(({ label, count, color }) => (
              <div key={label} className="glass-card px-3 py-1.5 flex items-center gap-2">
                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
                <span className="text-xs text-white/50">{label}:</span>
                <span className="text-xs font-bold text-white">{count}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Side panel */}
      <div className="w-72 border-l border-white/[0.06] bg-[#060f21] flex flex-col overflow-hidden">

        <div className="p-4 border-b border-white/[0.06]">
          <h2 className="text-sm font-semibold text-white">Network Nodes</h2>
          <p className="text-xs text-white/40 mt-0.5">Click a node on the map for details</p>
        </div>

        {/* Node list */}
        <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
          {network?.nodes.map((node) => (
            <button
              key={node.id}
              onClick={() => setSelectedNode(prev => prev?.id === node.id ? null : node)}
              className={cn(
                'w-full text-left px-3 py-2.5 rounded-lg border transition-all duration-200',
                selectedNode?.id === node.id
                  ? 'border-cyan-500/40 bg-cyan-500/[0.08]'
                  : 'border-transparent hover:bg-white/[0.03] hover:border-white/[0.08]'
              )}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <StatusIndicator status={node.status} size="sm" />
                  <div>
                    <div className="text-xs font-semibold text-white/90">{node.id}</div>
                    <div className="text-[10px] text-white/30">{node.name}</div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-xs font-mono text-white/70">{node.pressure.toFixed(2)}</div>
                  <div className="text-[10px] text-white/30">bar</div>
                </div>
              </div>
            </button>
          )) ?? (
            <div className="text-center text-white/20 text-xs py-8">Loading network...</div>
          )}
        </div>

        {/* Selected node detail */}
        {selectedNode && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="border-t border-white/[0.06] p-4 bg-[#040d1a]"
          >
            <div className="flex items-center justify-between mb-3">
              <div>
                <div className="font-semibold text-white">{selectedNode.name}</div>
                <div className="text-xs text-white/40 font-mono">{selectedNode.id}</div>
              </div>
              <span className={cn('text-xs px-2 py-0.5 rounded-full border capitalize', getNodeStatusBg(selectedNode.status))}>
                {selectedNode.status}
              </span>
            </div>

            <div className="space-y-2">
              {[
                { label: 'Pressure',   value: formatPressure(selectedNode.pressure),          alert: false },
                { label: 'Baseline',   value: formatPressure(selectedNode.pressure_baseline), alert: false },
                { label: 'Drop',       value: formatPressure(selectedNode.pressure_drop),     alert: selectedNode.pressure_drop > 0.3 },
                { label: 'Demand',     value: formatFlow(selectedNode.demand),                alert: false },
                { label: 'Head',       value: `${selectedNode.head.toFixed(1)} m`,            alert: false },
                { label: 'Elevation',  value: `${selectedNode.elevation} m ASL`,              alert: false },
              ].map(({ label, value, alert }) => (
                <div key={label} className="flex justify-between items-center py-1 border-b border-white/[0.04]">
                  <span className="text-xs text-white/40">{label}</span>
                  <span className={cn('text-xs font-mono font-medium', alert ? 'text-red-400' : 'text-white/80')}>{value}</span>
                </div>
              ))}
            </div>

            {selectedNode.is_anomaly && (
              <div className="mt-3 px-3 py-2 bg-red-500/10 border border-red-500/20 rounded-lg">
                <div className="text-xs text-red-400 font-medium">⚠ Pressure Anomaly Detected</div>
                <div className="text-[10px] text-red-400/70 mt-0.5">
                  Drop of {formatPressure(selectedNode.pressure_drop)} below baseline
                </div>
              </div>
            )}
          </motion.div>
        )}
      </div>
    </div>
  )
}
