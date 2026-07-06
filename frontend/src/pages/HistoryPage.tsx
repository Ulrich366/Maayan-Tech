/**
 * History Page — Timeline of all detected leak events.
 */

import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { History, AlertTriangle, CheckCircle, Trash2, RefreshCw } from 'lucide-react'
import { useHistory } from '../hooks/useApi'
import { HistoryEvent } from '../types'
import { getSeverityColor, formatPressure, formatFlow, cn } from '../utils'

export function HistoryPage() {
  const { fetchHistory, clearHistory, history, loading } = useHistory()
  const [severityFilter, setSeverityFilter] = useState<string>('')

  useEffect(() => {
    fetchHistory(100, severityFilter || undefined)
  }, [severityFilter])

  const events = history?.events ?? []

  return (
    <div className="p-6 space-y-6 overflow-y-auto h-full">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-blue-500/15 border border-blue-500/20">
            <History className="text-blue-400" size={20} />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-white">Event History</h1>
            <p className="text-xs text-white/40">{history?.total ?? 0} events recorded</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => fetchHistory(100, severityFilter || undefined)}
            className="p-2 rounded-lg bg-white/[0.04] border border-white/[0.08] text-white/50 hover:text-white/80 transition-colors"
          >
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          </button>
          <button
            onClick={() => { clearHistory(); fetchHistory(100) }}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-xs hover:bg-red-500/20 transition-colors"
          >
            <Trash2 size={14} />
            Clear
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-white/40">Filter by severity:</span>
        {['', 'low', 'medium', 'high', 'burst'].map((sev) => (
          <button
            key={sev}
            onClick={() => setSeverityFilter(sev)}
            className={cn(
              'px-3 py-1.5 rounded-full text-xs font-medium border transition-all duration-200 capitalize',
              severityFilter === sev
                ? 'border-cyan-500/40 bg-cyan-500/15 text-cyan-400'
                : 'border-white/10 text-white/40 hover:border-white/20 hover:text-white/60'
            )}
          >
            {sev || 'All'}
          </button>
        ))}
      </div>

      {/* Timeline */}
      {events.length === 0 ? (
        <div className="glass-card p-12 text-center">
          <CheckCircle className="w-12 h-12 text-emerald-500/30 mx-auto mb-3" />
          <p className="text-white/30 text-sm">No leak events recorded yet.</p>
          <p className="text-white/20 text-xs mt-1">Try switching to a leak scenario to generate events.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {events.map((event, i) => (
            <EventCard key={`${event.timestamp}-${i}`} event={event} index={i} />
          ))}
        </div>
      )}
    </div>
  )
}

function EventCard({ event, index }: { event: HistoryEvent; index: number }) {
  const [expanded, setExpanded] = useState(false)

  const severityBorder = {
    none:   'border-white/10',
    low:    'border-amber-500/20',
    medium: 'border-orange-500/30',
    high:   'border-red-500/30',
    burst:  'border-red-600/40',
  }[event.severity] || 'border-white/10'

  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.03 }}
      className={cn('glass-card border overflow-hidden', severityBorder)}
    >
      <button
        className="w-full p-4 text-left"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3">
          {/* Time indicator */}
          <div className="flex-shrink-0 w-24 text-right">
            <div className="text-xs font-mono text-white/60">
              {new Date(event.recorded_at).toLocaleDateString()}
            </div>
            <div className="text-[10px] font-mono text-white/30">
              {new Date(event.recorded_at).toLocaleTimeString()}
            </div>
          </div>

          {/* Line connector */}
          <div className="flex-shrink-0 flex flex-col items-center">
            <div className={cn(
              'w-3 h-3 rounded-full',
              event.severity === 'burst' ? 'bg-red-500' :
              event.severity === 'high' ? 'bg-red-400' :
              event.severity === 'medium' ? 'bg-orange-400' :
              event.severity === 'low' ? 'bg-amber-400' : 'bg-emerald-400'
            )} />
          </div>

          {/* Event info */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <AlertTriangle size={13} className={getSeverityColor(event.severity)} />
              <span className={cn('text-sm font-semibold', getSeverityColor(event.severity))}>
                {event.severity.toUpperCase()} LEAK
              </span>
              <span className="text-xs text-white/40 truncate">{event.location}</span>
            </div>
            <div className="flex gap-4 mt-1 text-xs text-white/40">
              <span>Prob: <span className="text-white/60">{event.probability.toFixed(0)}%</span></span>
              <span>Drop: <span className="text-white/60">{formatPressure(event.pressure_drop)}</span></span>
              <span>Loss: <span className="text-red-400">{formatFlow(event.estimated_flow_loss)}</span></span>
            </div>
          </div>

          <span className="text-xs text-white/20">{expanded ? '▲' : '▼'}</span>
        </div>
      </button>

      {expanded && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          className="border-t border-white/[0.06] px-4 pb-4 pt-3"
        >
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
            <div><span className="text-white/30">Node ID</span><div className="font-mono text-white/70 mt-0.5">{event.node_id || '—'}</div></div>
            <div><span className="text-white/30">Pipe ID</span><div className="font-mono text-white/70 mt-0.5">{event.pipe_id || '—'}</div></div>
            <div><span className="text-white/30">AI Confidence</span><div className="font-mono text-white/70 mt-0.5">{event.confidence.toFixed(1)}%</div></div>
            <div><span className="text-white/30">Method</span><div className="font-mono text-white/70 mt-0.5 capitalize">{event.detection_method}</div></div>
            {event.affected_nodes.length > 0 && (
              <div className="col-span-full">
                <span className="text-white/30">Affected nodes: </span>
                <span className="font-mono text-white/60">{event.affected_nodes.join(', ')}</span>
              </div>
            )}
          </div>
        </motion.div>
      )}
    </motion.div>
  )
}
