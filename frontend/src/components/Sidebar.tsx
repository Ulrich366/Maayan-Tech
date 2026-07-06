import { NavLink } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  LayoutDashboard, Network, BarChart3, FileText,
  History, Settings, Wifi, Droplets
} from 'lucide-react'
import { cn } from '../utils'

const NAV_ITEMS = [
  { path: '/',         label: 'Dashboard',    icon: LayoutDashboard },
  { path: '/network',  label: 'Live Network', icon: Network         },
  { path: '/pressure', label: 'Pressure',     icon: BarChart3       },
  { path: '/report',   label: 'AI Report',    icon: FileText        },
  { path: '/history',  label: 'History',      icon: History         },
  { path: '/iot',      label: 'IoT Nodes',    icon: Wifi            },
  { path: '/settings', label: 'Settings',     icon: Settings        },
]

interface SidebarProps {
  collapsed?: boolean
}

export function Sidebar({ collapsed = false }: SidebarProps) {
  return (
    <aside className={cn(
      'flex flex-col h-full bg-[#060f21] border-r border-white/[0.06] transition-all duration-300',
      collapsed ? 'w-16' : 'w-60'
    )}>
      {/* Logo */}
      <div className="flex items-center gap-3 px-5 py-5 border-b border-white/[0.06]">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-400 to-blue-500 flex items-center justify-center flex-shrink-0">
          <Droplets className="w-4.5 h-4.5 text-white" size={18} />
        </div>
        {!collapsed && (
          <div>
            <div className="font-bold text-white text-sm tracking-wide">MAAYAN</div>
            <div className="text-[10px] text-white/40 tracking-widest uppercase">Water Intel</div>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map(({ path, label, icon: Icon }) => (
          <NavLink
            key={path}
            to={path}
            end={path === '/'}
            className={({ isActive }) => cn(
              'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200',
              isActive
                ? 'bg-cyan-500/15 text-cyan-400 border border-cyan-500/20'
                : 'text-white/50 hover:text-white/80 hover:bg-white/[0.04]',
              collapsed && 'justify-center px-2'
            )}
          >
            {({ isActive }) => (
              <>
                <Icon
                  size={18}
                  className={cn(isActive ? 'text-cyan-400' : 'text-white/50', 'flex-shrink-0')}
                />
                {!collapsed && <span>{label}</span>}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      {!collapsed && (
        <div className="px-5 py-4 border-t border-white/[0.06]">
          <div className="text-[10px] text-white/25 text-center">
            Maayan © 2026
          </div>
        </div>
      )}
    </aside>
  )
}
