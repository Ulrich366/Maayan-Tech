import { cn } from '../../utils'
import { NodeStatus } from '../../types'

interface StatusIndicatorProps {
  status: NodeStatus
  size?: 'sm' | 'md' | 'lg'
  pulse?: boolean
  label?: string
  className?: string
}

const STATUS_CONFIG = {
  normal:  { color: 'bg-emerald-400', label: 'Normal',  glow: 'shadow-emerald-400/50' },
  warning: { color: 'bg-amber-400',   label: 'Warning', glow: 'shadow-amber-400/50'   },
  leak:    { color: 'bg-red-500',     label: 'Leak',    glow: 'shadow-red-500/50'     },
  burst:   { color: 'bg-red-600',     label: 'Burst',   glow: 'shadow-red-600/60'     },
}

const SIZE_CONFIG = {
  sm: 'w-2 h-2',
  md: 'w-3 h-3',
  lg: 'w-4 h-4',
}

export function StatusIndicator({ status, size = 'md', pulse = true, label, className }: StatusIndicatorProps) {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.normal
  const sizeClass = SIZE_CONFIG[size]

  return (
    <span className={cn('inline-flex items-center gap-2', className)}>
      <span className="relative flex">
        {pulse && (status === 'leak' || status === 'burst') && (
          <span className={cn(
            'animate-ping absolute inline-flex h-full w-full rounded-full opacity-75',
            cfg.color,
          )} />
        )}
        <span className={cn(
          'relative inline-flex rounded-full shadow-lg',
          sizeClass,
          cfg.color,
          cfg.glow,
        )} />
      </span>
      {label !== undefined && (
        <span className="text-xs text-white/60">{label ?? cfg.label}</span>
      )}
    </span>
  )
}
