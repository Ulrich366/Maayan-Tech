/**
 * NetworkDiagram — SVG-based digital twin of the active simulated water
 * network (Douala, Bafoussam, ...). Renders nodes, pipes, animated flow,
 * leak indicators. Reservoir/tank labels and the title are driven by the
 * live network snapshot, so this component works unchanged for any city.
 */

import { useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { NetworkSnapshot, NodeState, PipeState } from '../types'
import { getNodeStatusColor, formatPressure, formatFlow, cn } from '../utils'

interface NetworkDiagramProps {
  network: NetworkSnapshot | null
  width?: number
  height?: number
  onNodeClick?: (node: NodeState) => void
}

// SVG viewport dimensions (matches coordinate space in simulator)
const VIEW_W = 1200
const VIEW_H = 850

// Node radius
const NODE_R = 22

function getPipeColor(status: string): string {
  switch (status) {
    case 'burst':  return '#dc2626'
    case 'leak':   return '#ef4444'
    case 'warning':return '#f59e0b'
    default:       return '#1e3a5f'
  }
}

function getPipeWidth(status: string): number {
  switch (status) {
    case 'burst': return 6
    case 'leak':  return 4
    default:      return 2.5
  }
}

interface NodeTooltipProps {
  node: NodeState
  x: number
  y: number
}

function NodeTooltip({ node, x, y }: NodeTooltipProps) {
  const statusColors = {
    normal:  'border-emerald-500/40 bg-emerald-500/10',
    warning: 'border-amber-500/40 bg-amber-500/10',
    leak:    'border-red-500/40 bg-red-500/10',
    burst:   'border-red-600/50 bg-red-600/15',
  }

  const flip = x > VIEW_W * 0.65

  return (
    <motion.foreignObject
      x={flip ? x - 200 : x + NODE_R + 8}
      y={Math.max(10, y - 60)}
      width={190}
      height={160}
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.9 }}
    >
      <div className={cn(
        'p-3 rounded-xl border backdrop-blur-sm text-xs space-y-1.5',
        statusColors[node.status] || statusColors.normal,
      )}>
        <div className="font-bold text-white text-sm">{node.name}</div>
        <div className="text-white/50 text-[10px] font-mono">{node.id}</div>
        <div className="border-t border-white/10 pt-1.5 space-y-1">
          <Row label="Pressure" value={formatPressure(node.pressure)} />
          <Row label="Baseline" value={formatPressure(node.pressure_baseline)} />
          <Row label="Drop" value={formatPressure(node.pressure_drop)} alert={node.pressure_drop > 0.3} />
          <Row label="Demand" value={`${node.demand.toFixed(2)} L/s`} />
          <Row label="Elevation" value={`${node.elevation} m`} />
        </div>
        <div className={cn(
          'capitalize text-center py-0.5 rounded font-semibold text-[10px] mt-1',
          node.status === 'normal' ? 'text-emerald-400' :
          node.status === 'warning' ? 'text-amber-400' : 'text-red-400'
        )}>
          ● {node.status.toUpperCase()}
        </div>
      </div>
    </motion.foreignObject>
  )
}

function Row({ label, value, alert }: { label: string; value: string; alert?: boolean }) {
  return (
    <div className="flex justify-between gap-2">
      <span className="text-white/40">{label}</span>
      <span className={cn('font-mono font-medium', alert ? 'text-red-400' : 'text-white/80')}>{value}</span>
    </div>
  )
}

export function NetworkDiagram({ network, width, height, onNodeClick }: NetworkDiagramProps) {
  const [hoveredNode, setHoveredNode] = useState<NodeState | null>(null)
  const [selectedNode, setSelectedNode] = useState<NodeState | null>(null)

  const handleNodeClick = useCallback((node: NodeState) => {
    setSelectedNode(prev => prev?.id === node.id ? null : node)
    onNodeClick?.(node)
  }, [onNodeClick])

  if (!network) {
    return (
      <div className="flex items-center justify-center h-full text-white/30 text-sm">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-cyan-500/30 border-t-cyan-400 rounded-full animate-spin mx-auto mb-3" />
          Connecting to simulation...
        </div>
      </div>
    )
  }

  const nodeMap = Object.fromEntries(network.nodes.map(n => [n.id, n]))

  // Reservoir/Tank pseudo-nodes — positions/labels come from the active
  // network's live snapshot, so they're correct for whichever city
  // (Douala, Bafoussam, ...) is currently selected.
  const specialNodes = network.infrastructure?.length ? network.infrastructure : [
    { id: 'R1', label: 'Reservoir\nSource', x: 200, y: 500, type: 'reservoir' as const },
    { id: 'T1', label: 'Tank', x: 300, y: 350, type: 'tank' as const },
  ]

  const getCoord = (id: string) => {
    const n = nodeMap[id]
    if (n) return { x: n.x, y: n.y }
    const s = specialNodes.find(sn => sn.id === id)
    return s ? { x: s.x, y: s.y } : { x: 0, y: 0 }
  }

  return (
    <div className="w-full h-full relative">
      <svg
        viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
        className="w-full h-full"
        style={{ width: width, height: height }}
      >
        <defs>
          {/* Grid pattern */}
          <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
            <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(255,255,255,0.03)" strokeWidth="1" />
          </pattern>

          {/* Glow filter */}
          <filter id="glow-red">
            <feGaussianBlur stdDeviation="4" result="coloredBlur" />
            <feMerge><feMergeNode in="coloredBlur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <filter id="glow-green">
            <feGaussianBlur stdDeviation="3" result="coloredBlur" />
            <feMerge><feMergeNode in="coloredBlur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <filter id="glow-cyan">
            <feGaussianBlur stdDeviation="3" result="coloredBlur" />
            <feMerge><feMergeNode in="coloredBlur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>

          {/* Arrow markers */}
          <marker id="arrow-normal" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto">
            <path d="M0,0 L0,6 L6,3 z" fill="#1e3a5f" />
          </marker>
          <marker id="arrow-leak" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto">
            <path d="M0,0 L0,6 L6,3 z" fill="#ef4444" />
          </marker>
        </defs>

        {/* Background */}
        <rect width={VIEW_W} height={VIEW_H} fill="url(#grid)" />
        <rect width={VIEW_W} height={VIEW_H} fill="rgba(4,13,26,0.6)" />

        {/* Title */}
        <text x="20" y="30" fill="rgba(255,255,255,0.3)" fontSize="11" fontFamily="Inter, sans-serif" fontWeight="500">
          {network.title || 'WATER DISTRIBUTION NETWORK'}
        </text>

        {/* Pipes */}
        {network.pipes.map((pipe) => {
          const from = getCoord(pipe.start_node)
          const to = getCoord(pipe.end_node)
          const color = getPipeColor(pipe.status)
          const width = getPipeWidth(pipe.status)
          const isLeak = pipe.status === 'leak' || pipe.status === 'burst'

          return (
            <g key={pipe.id}>
              {/* Pipe background glow for leaks */}
              {isLeak && (
                <line
                  x1={from.x} y1={from.y} x2={to.x} y2={to.y}
                  stroke={color}
                  strokeWidth={width + 8}
                  strokeOpacity={0.15}
                  strokeLinecap="round"
                  filter="url(#glow-red)"
                />
              )}

              {/* Pipe line */}
              <line
                x1={from.x} y1={from.y} x2={to.x} y2={to.y}
                stroke={color}
                strokeWidth={width}
                strokeLinecap="round"
                strokeOpacity={0.85}
              />

              {/* Animated flow */}
              <line
                x1={from.x} y1={from.y} x2={to.x} y2={to.y}
                stroke={isLeak ? '#ef4444' : '#22d3ee'}
                strokeWidth={isLeak ? 2 : 1.5}
                strokeLinecap="round"
                strokeOpacity={isLeak ? 0.8 : 0.4}
                strokeDasharray={isLeak ? '5 3' : '8 6'}
                className={isLeak ? 'pipe-flow-fast' : 'pipe-flow'}
              />

              {/* Pipe ID label */}
              <text
                x={(from.x + to.x) / 2}
                y={(from.y + to.y) / 2 - 5}
                fill={isLeak ? '#ef4444' : 'rgba(255,255,255,0.2)'}
                fontSize="9"
                textAnchor="middle"
                fontFamily="JetBrains Mono, monospace"
              >
                {pipe.id}
              </text>
            </g>
          )
        })}

        {/* Special nodes: Reservoirs & Tanks */}
        {specialNodes.map((sn) => (
          <g key={sn.id}>
            <rect
              x={sn.x - 20} y={sn.y - 16}
              width={40} height={32}
              rx={4}
              fill={sn.type === 'reservoir' ? '#0c2040' : '#0a1e38'}
              stroke={sn.type === 'reservoir' ? '#22d3ee' : '#60a5fa'}
              strokeWidth={1.5}
              strokeOpacity={0.6}
            />
            <text x={sn.x} y={sn.y + 4} textAnchor="middle" fill="#22d3ee" fontSize="10" fontWeight="600" fontFamily="Inter, sans-serif">
              {sn.type === 'reservoir' ? '≋' : '▣'}
            </text>
            <text x={sn.x} y={sn.y + 30} textAnchor="middle" fill="rgba(255,255,255,0.35)" fontSize="9" fontFamily="Inter, sans-serif">
              {sn.id}
            </text>
          </g>
        ))}

        {/* Junction Nodes */}
        {network.nodes.map((node) => {
          const color = getNodeStatusColor(node.status)
          const isSelected = selectedNode?.id === node.id
          const isHovered = hoveredNode?.id === node.id
          const isLeak = node.status === 'leak' || node.status === 'burst'

          return (
            <g
              key={node.id}
              onClick={() => handleNodeClick(node)}
              onMouseEnter={() => setHoveredNode(node)}
              onMouseLeave={() => setHoveredNode(null)}
              style={{ cursor: 'pointer' }}
            >
              {/* Pulse rings for leak/burst */}
              {isLeak && (
                <>
                  <circle cx={node.x} cy={node.y} r={NODE_R + 12} fill="none" stroke={color} strokeWidth={1} strokeOpacity={0.15} className="animate-ping" />
                  <circle cx={node.x} cy={node.y} r={NODE_R + 6} fill="none" stroke={color} strokeWidth={1.5} strokeOpacity={0.3} className="animate-ping-slow" />
                </>
              )}

              {/* Selection ring */}
              {isSelected && (
                <circle cx={node.x} cy={node.y} r={NODE_R + 6} fill="none" stroke="#22d3ee" strokeWidth={2} strokeOpacity={0.8} />
              )}

              {/* Node background */}
              <circle
                cx={node.x} cy={node.y} r={NODE_R}
                fill={`${color}18`}
                stroke={color}
                strokeWidth={isHovered || isSelected ? 2.5 : 1.8}
                filter={isLeak ? 'url(#glow-red)' : isHovered ? 'url(#glow-cyan)' : undefined}
              />

              {/* Inner dot */}
              <circle cx={node.x} cy={node.y} r={6} fill={color} opacity={0.9} />

              {/* Node ID */}
              <text x={node.x} y={node.y - NODE_R - 5} textAnchor="middle" fill="rgba(255,255,255,0.6)" fontSize="10" fontWeight="600" fontFamily="Inter, sans-serif">
                {node.id}
              </text>

              {/* Pressure reading */}
              <text x={node.x} y={node.y + NODE_R + 14} textAnchor="middle" fill={isLeak ? color : 'rgba(255,255,255,0.4)'} fontSize="9" fontFamily="JetBrains Mono, monospace">
                {node.pressure.toFixed(2)} bar
              </text>

              {/* Zone name */}
              <text x={node.x} y={node.y + NODE_R + 24} textAnchor="middle" fill="rgba(255,255,255,0.25)" fontSize="8" fontFamily="Inter, sans-serif">
                {node.name}
              </text>
            </g>
          )
        })}

        {/* Tooltips */}
        <AnimatePresence>
          {(hoveredNode || selectedNode) && (() => {
            const n = selectedNode || hoveredNode!
            return <NodeTooltip key={n.id} node={n} x={n.x} y={n.y} />
          })()}
        </AnimatePresence>

        {/* Legend */}
        <g transform="translate(900, 40)">
          <rect x={0} y={0} width={180} height={130} rx={8} fill="rgba(6,15,33,0.9)" stroke="rgba(255,255,255,0.08)" strokeWidth={1} />
          <text x={90} y={20} textAnchor="middle" fill="rgba(255,255,255,0.5)" fontSize="10" fontWeight="600" fontFamily="Inter, sans-serif">LEGEND</text>
          {[
            { color: '#10b981', label: 'Normal Operation' },
            { color: '#f59e0b', label: 'Pressure Warning' },
            { color: '#ef4444', label: 'Leak Detected' },
            { color: '#dc2626', label: 'Pipe Burst' },
          ].map(({ color, label }, i) => (
            <g key={label} transform={`translate(14, ${35 + i * 22})`}>
              <circle cx={8} cy={8} r={6} fill={`${color}20`} stroke={color} strokeWidth={1.5} />
              <circle cx={8} cy={8} r={3} fill={color} />
              <text x={20} y={12} fill="rgba(255,255,255,0.5)" fontSize="10" fontFamily="Inter, sans-serif">{label}</text>
            </g>
          ))}
        </g>

        {/* Scenario badge */}
        <g transform={`translate(20, ${VIEW_H - 40})`}>
          <rect x={0} y={0} width={180} height={26} rx={4} fill="rgba(34,211,238,0.08)" stroke="rgba(34,211,238,0.2)" strokeWidth={1} />
          <text x={90} y={17} textAnchor="middle" fill="#22d3ee" fontSize="10" fontWeight="600" fontFamily="Inter, sans-serif">
            SCENARIO: {network.scenario.toUpperCase()}
          </text>
        </g>
      </svg>
    </div>
  )
}
