import { motion } from 'framer-motion'
import { cn } from '../../utils'

interface MetricCardProps {
  title: string
  value: string | number
  unit?: string
  subtitle?: string
  icon?: React.ReactNode
  trend?: 'up' | 'down' | 'stable'
  alert?: boolean
  className?: string
  color?: string
}

export function MetricCard({
  title, value, unit, subtitle, icon, trend, alert, className, color
}: MetricCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        'glass-card p-5 relative overflow-hidden',
        alert && 'border-red-500/40 bg-red-500/[0.04]',
        className
      )}
    >
      {/* Background glow */}
      {color && (
        <div
          className="absolute inset-0 opacity-5 pointer-events-none"
          style={{ background: `radial-gradient(ellipse at top left, ${color}, transparent 70%)` }}
        />
      )}

      <div className="relative z-10">
        <div className="flex items-start justify-between mb-3">
          <span className="text-xs font-medium text-white/50 uppercase tracking-wider">{title}</span>
          {icon && (
            <div className="p-2 rounded-lg bg-white/[0.06]" style={{ color: color || '#22d3ee' }}>
              {icon}
            </div>
          )}
        </div>

        <div className="flex items-baseline gap-1.5">
          <span
            className="text-3xl font-bold tabular-nums"
            style={{ color: color || 'white' }}
          >
            {value}
          </span>
          {unit && <span className="text-sm text-white/40 font-medium">{unit}</span>}
        </div>

        {subtitle && (
          <p className="mt-2 text-xs text-white/40">{subtitle}</p>
        )}

        {trend && (
          <div className={cn(
            'mt-2 text-xs font-medium',
            trend === 'up' && 'text-red-400',
            trend === 'down' && 'text-emerald-400',
            trend === 'stable' && 'text-cyan-400',
          )}>
            {trend === 'up' && '↑'} {trend === 'down' && '↓'} {trend === 'stable' && '→'} {' '}
            {trend === 'stable' ? 'Stable' : trend === 'up' ? 'Increasing' : 'Decreasing'}
          </div>
        )}
      </div>
    </motion.div>
  )
}
