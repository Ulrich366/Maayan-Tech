import { cn } from '../../utils'

interface BadgeProps {
  children: React.ReactNode
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info'
  className?: string
}

export function Badge({ children, variant = 'default', className }: BadgeProps) {
  const variants = {
    default: 'bg-white/10 text-white/80 border-white/20',
    success: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40',
    warning: 'bg-amber-500/20 text-amber-400 border-amber-500/40',
    danger:  'bg-red-500/20 text-red-400 border-red-500/40',
    info:    'bg-cyan-500/20 text-cyan-400 border-cyan-500/40',
  }

  return (
    <span className={cn(
      'inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold border',
      variants[variant],
      className
    )}>
      {children}
    </span>
  )
}
