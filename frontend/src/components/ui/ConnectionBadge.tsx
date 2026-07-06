import { cn } from '../../utils'

interface ConnectionBadgeProps {
  isConnected: boolean
  attempt?: number
}

export function ConnectionBadge({ isConnected, attempt }: ConnectionBadgeProps) {
  return (
    <div className={cn(
      'flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium border',
      isConnected
        ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
        : 'bg-red-500/10 border-red-500/30 text-red-400'
    )}>
      <span className={cn(
        'w-2 h-2 rounded-full',
        isConnected ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'
      )} />
      {isConnected ? 'LIVE' : attempt ? `Reconnecting... (${attempt})` : 'Disconnected'}
    </div>
  )
}
