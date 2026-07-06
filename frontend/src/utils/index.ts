import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
import { NodeStatus, Severity, AlertLevel } from '../types'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatPressure(value: number): string {
  return `${value.toFixed(2)} bar`
}

export function formatFlow(value: number): string {
  return `${value.toFixed(1)} L/s`
}

export function formatPercent(value: number): string {
  return `${value.toFixed(0)}%`
}

export function formatTime(date: Date): string {
  return date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function getNodeStatusColor(status: NodeStatus): string {
  switch (status) {
    case 'normal':  return '#10b981' // emerald
    case 'warning': return '#f59e0b' // amber
    case 'leak':    return '#ef4444' // red
    case 'burst':   return '#dc2626' // darker red
    default:        return '#6b7280'
  }
}

export function getNodeStatusBg(status: NodeStatus): string {
  switch (status) {
    case 'normal':  return 'bg-emerald-500/20 border-emerald-500/50 text-emerald-400'
    case 'warning': return 'bg-amber-500/20 border-amber-500/50 text-amber-400'
    case 'leak':    return 'bg-red-500/20 border-red-500/50 text-red-400'
    case 'burst':   return 'bg-red-700/30 border-red-600/60 text-red-300'
    default:        return 'bg-gray-500/20 border-gray-500/50 text-gray-400'
  }
}

export function getSeverityColor(severity: Severity | AlertLevel): string {
  switch (severity) {
    case 'none':   case 'green':  return 'text-emerald-400'
    case 'low':    case 'yellow': return 'text-amber-400'
    case 'medium': case 'orange': return 'text-orange-400'
    case 'high':   case 'red':    return 'text-red-400'
    case 'burst':                  return 'text-red-300'
    default:                       return 'text-gray-400'
  }
}

export function getHealthColor(health: number): string {
  if (health >= 90) return '#10b981'
  if (health >= 70) return '#f59e0b'
  if (health >= 50) return '#f97316'
  return '#ef4444'
}

export function getScenarioLabel(scenario: string): string {
  switch (scenario) {
    case 'normal': return 'Normal Operation'
    case 'small':  return 'Small Leak (J7)'
    case 'medium': return 'Medium Leak (J7)'
    case 'burst':  return 'Pipe Burst (P7)'
    default:       return scenario
  }
}

export function getProbabilityBadgeColor(prob: number): string {
  if (prob >= 80) return 'bg-red-500/20 text-red-400 border-red-500/40'
  if (prob >= 50) return 'bg-orange-500/20 text-orange-400 border-orange-500/40'
  if (prob >= 20) return 'bg-amber-500/20 text-amber-400 border-amber-500/40'
  return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40'
}

export function truncateText(text: string, maxLen: number): string {
  return text.length > maxLen ? `${text.slice(0, maxLen)}...` : text
}
