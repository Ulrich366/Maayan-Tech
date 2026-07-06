import { motion, AnimatePresence } from 'framer-motion'
import { AlertTriangle, MapPin, Droplets, Activity, X } from 'lucide-react'
import { LeakReport } from '../types'
import { getSeverityColor, formatPressure, formatFlow, formatPercent, cn } from '../utils'

interface LeakAlertProps {
  report: LeakReport | null
  onDismiss?: () => void
}

const SEVERITY_STYLES = {
  none:   'border-emerald-500/30 bg-emerald-500/[0.05]',
  low:    'border-amber-500/40 bg-amber-500/[0.06]',
  medium: 'border-orange-500/40 bg-orange-500/[0.07]',
  high:   'border-red-500/40 bg-red-500/[0.08]',
  burst:  'border-red-600/50 bg-red-600/[0.10]',
}

const SEVERITY_ICON_COLORS = {
  none:   'text-emerald-400',
  low:    'text-amber-400',
  medium: 'text-orange-400',
  high:   'text-red-400',
  burst:  'text-red-300',
}

export function LeakAlert({ report, onDismiss }: LeakAlertProps) {
  if (!report) return null

  const isLeak = report.detected
  const sev = report.severity

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={report.timestamp}
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -10 }}
        className={cn(
          'glass-card p-4 border relative',
          isLeak ? SEVERITY_STYLES[sev] || SEVERITY_STYLES.medium : 'border-emerald-500/20 bg-emerald-500/[0.04]'
        )}
      >
        {onDismiss && (
          <button
            onClick={onDismiss}
            className="absolute top-3 right-3 text-white/30 hover:text-white/60 transition-colors"
          >
            <X size={14} />
          </button>
        )}

        <div className="flex items-start gap-3">
          <div className={cn(
            'p-2 rounded-lg flex-shrink-0',
            isLeak ? 'bg-red-500/20' : 'bg-emerald-500/20'
          )}>
            {isLeak ? (
              <AlertTriangle
                size={20}
                className={cn(SEVERITY_ICON_COLORS[sev], isLeak && 'animate-pulse')}
              />
            ) : (
              <Activity size={20} className="text-emerald-400" />
            )}
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <h3 className={cn(
                'font-semibold text-sm',
                isLeak ? getSeverityColor(sev) : 'text-emerald-400'
              )}>
                {isLeak ? `${sev.toUpperCase()} LEAK DETECTED` : 'NETWORK NOMINAL'}
              </h3>
              <span className={cn(
                'text-xs px-2 py-0.5 rounded-full border font-mono',
                isLeak ? 'border-red-500/40 bg-red-500/10 text-red-400' : 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400'
              )}>
                {formatPercent(report.probability)} probability
              </span>
            </div>

            {isLeak ? (
              <div className="grid grid-cols-2 gap-x-6 gap-y-1 mt-2">
                <DataRow icon={<MapPin size={12} />} label="Location" value={report.location} />
                <DataRow icon={<Droplets size={12} />} label="Flow Loss" value={formatFlow(report.estimated_flow_loss)} alert />
                <DataRow icon={<Activity size={12} />} label="Pressure Drop" value={formatPressure(report.pressure_drop)} alert />
                <DataRow label="AI Confidence" value={formatPercent(report.confidence)} />
              </div>
            ) : (
              <p className="text-xs text-white/40 mt-1">
                All pressure readings within normal parameters. No anomalies detected.
              </p>
            )}
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  )
}

function DataRow({ label, value, icon, alert }: {
  label: string; value: string; icon?: React.ReactNode; alert?: boolean
}) {
  return (
    <div className="flex items-center gap-1.5">
      {icon && <span className="text-white/30">{icon}</span>}
      <span className="text-white/40 text-xs">{label}:</span>
      <span className={cn('text-xs font-semibold font-mono', alert ? 'text-red-400' : 'text-white/80')}>
        {value}
      </span>
    </div>
  )
}
