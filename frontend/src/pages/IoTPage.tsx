/**
 * IoT Nodes Page — Sensor node registry with Phase 2 hardware readiness.
 */

import { useEffect } from 'react'
import { motion } from 'framer-motion'
import { Wifi, Battery, Signal, Clock, Cpu, Radio } from 'lucide-react'
import { useIoTNodes } from '../hooks/useApi'
import { StatusIndicator } from '../components/ui/StatusIndicator'
import { NodeStatus } from '../types'
import { cn } from '../utils'

export function IoTPage() {
  const { fetchNodes, nodes, liveCount, loading } = useIoTNodes()

  useEffect(() => {
    fetchNodes()
    const interval = setInterval(fetchNodes, 5000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="p-6 space-y-6 overflow-y-auto h-full">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-violet-500/15 border border-violet-500/20">
            <Wifi className="text-violet-400" size={20} />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-white">IoT Sensor Nodes</h1>
            <p className="text-xs text-white/40">Phase 1: Simulated · Phase 2: ESP32 + LoRa hardware</p>
          </div>
        </div>

        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-amber-500/10 border border-amber-500/20">
          <Radio size={12} className="text-amber-400" />
          <span className="text-xs text-amber-400 font-medium">
            {liveCount > 0
              ? `${liveCount} Live IoT Node(s)`
              : 'Simulation Mode — HTTP/MQTT ingest ready'}
          </span>
        </div>
      </div>

      {/* Phase 2 notice */}
      <div className="glass-card p-4 border border-violet-500/20 bg-violet-500/[0.04]">
        <div className="flex gap-3">
          <Cpu className="text-violet-400 flex-shrink-0 mt-0.5" size={16} />
          <div>
            <p className="text-sm font-medium text-violet-400">Phase 2 Hardware Integration Ready</p>
            <p className="text-xs text-white/40 mt-1">
              Live hardware connects via <span className="font-mono text-white/50">POST /api/iot/telemetry</span> (HTTP)
              or MQTT topic <span className="font-mono text-white/50">maayan/sensors/&#123;node_id&#125;/pressure</span>.
              Fresh readings override simulation pressures on the dashboard within ~2s.
            </p>
            <div className="flex gap-3 mt-2">
              {['ESP32 Microcontroller', 'LoRa 915MHz', 'MQTT Protocol', 'Battery Powered'].map(tech => (
                <span key={tech} className="text-[10px] px-2 py-0.5 rounded bg-violet-500/15 border border-violet-500/20 text-violet-300">
                  {tech}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Node grid */}
      {loading && nodes.length === 0 ? (
        <div className="text-center text-white/30 py-8">
          <div className="w-8 h-8 border-2 border-violet-500/30 border-t-violet-400 rounded-full animate-spin mx-auto mb-3" />
          Loading sensor nodes...
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {(nodes as IoTNodeData[]).map((node, i) => (
            <NodeCard key={node.node_id} node={node} index={i} />
          ))}
        </div>
      )}
    </div>
  )
}

interface IoTNodeData {
  node_id: string
  name: string
  device_type: string
  battery_level: number
  rssi: number
  pressure: number
  status: NodeStatus
  last_seen: string
  firmware_version: string
}

function NodeCard({ node, index }: { node: IoTNodeData; index: number }) {
  const batteryColor =
    node.battery_level > 60 ? 'text-emerald-400' :
    node.battery_level > 30 ? 'text-amber-400' : 'text-red-400'

  const rssiColor =
    node.rssi > -60 ? 'text-emerald-400' :
    node.rssi > -75 ? 'text-amber-400' : 'text-red-400'

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      className={cn(
        'glass-card p-4 border transition-all hover:border-white/[0.12]',
        node.status === 'leak' || node.status === 'burst'
          ? 'border-red-500/30 bg-red-500/[0.04]'
          : 'border-white/[0.08]'
      )}
    >
      {/* Node header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <StatusIndicator status={node.status} size="sm" />
          <div>
            <div className="text-sm font-semibold text-white">{node.node_id}</div>
            <div className="text-xs text-white/40">{node.name}</div>
          </div>
        </div>
        <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/[0.06] border border-white/10 text-white/40 font-mono">
          {node.device_type}
        </span>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 gap-2 mb-3">
        <Metric
          icon={<Signal size={11} />}
          label="Pressure"
          value={`${node.pressure.toFixed(2)} bar`}
          color="text-cyan-400"
        />
        <Metric
          icon={<Battery size={11} />}
          label="Battery"
          value={`${node.battery_level.toFixed(0)}%`}
          color={batteryColor}
        />
        <Metric
          icon={<Wifi size={11} />}
          label="RSSI"
          value={`${node.rssi} dBm`}
          color={rssiColor}
        />
        <Metric
          icon={<Cpu size={11} />}
          label="Firmware"
          value={node.firmware_version}
          color="text-white/50"
        />
      </div>

      {/* Last seen */}
      <div className="flex items-center gap-1.5 text-[10px] text-white/25">
        <Clock size={10} />
        Last seen: {new Date(node.last_seen).toLocaleTimeString()}
      </div>

      {/* Battery bar */}
      <div className="mt-3">
        <div className="h-1 bg-white/[0.06] rounded-full overflow-hidden">
          <div
            className={cn('h-full rounded-full transition-all duration-500', batteryColor.replace('text-', 'bg-'))}
            style={{ width: `${node.battery_level}%` }}
          />
        </div>
      </div>
    </motion.div>
  )
}

function Metric({ icon, label, value, color }: { icon: React.ReactNode; label: string; value: string; color: string }) {
  return (
    <div className="bg-white/[0.03] rounded-lg px-2.5 py-2">
      <div className={cn('flex items-center gap-1 text-[10px] mb-0.5', color)}>
        {icon}
        <span className="text-white/30">{label}</span>
      </div>
      <div className={cn('text-xs font-mono font-medium', color)}>{value}</div>
    </div>
  )
}
