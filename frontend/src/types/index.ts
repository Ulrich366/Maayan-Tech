// ============================================================
// Maayan TypeScript Type Definitions
// ============================================================

export type NodeStatus = 'normal' | 'warning' | 'leak' | 'burst'
export type Scenario = 'normal' | 'small' | 'medium' | 'burst'
export type AlertLevel = 'green' | 'yellow' | 'orange' | 'red'
export type Severity = 'none' | 'low' | 'medium' | 'high' | 'burst'
export type Language = 'en' | 'fr'

// ── Network ──────────────────────────────────────────────────────────────────

export interface NodeState {
  id: string
  name: string
  pressure: number
  head: number
  demand: number
  elevation: number
  x: number
  y: number
  status: NodeStatus
  is_anomaly: boolean
  pressure_baseline: number
  pressure_drop: number
}

export interface PipeState {
  id: string
  start_node: string
  end_node: string
  flow: number
  velocity: number
  headloss: number
  length: number
  diameter: number
  status: 'normal' | 'warning' | 'leak' | 'burst'
}

export interface InfrastructureNode {
  id: string
  label: string
  x: number
  y: number
  type: 'reservoir' | 'tank'
}

export interface NetworkSnapshot {
  timestamp: number
  scenario: Scenario
  engine: 'epanet' | 'synthetic'
  city: string
  city_label: string
  title: string
  infrastructure: InfrastructureNode[]
  nodes: NodeState[]
  pipes: PipeState[]
  total_demand: number
  total_leakage: number
  system_health: number
  simulation_time: number
}

// ── Networks (simulated cities) ───────────────────────────────────────────────

export interface NetworkOption {
  id: string
  label: string
  inp_file: string
}

export interface NetworkListResponse {
  active: string
  networks: NetworkOption[]
}

// ── Leak Detection ────────────────────────────────────────────────────────────

export interface LeakReport {
  detected: boolean
  location: string
  node_id: string | null
  pipe_id: string | null
  probability: number
  severity: Severity
  pressure_drop: number
  estimated_flow_loss: number
  affected_nodes: string[]
  confidence: number
  detection_method: string
  timestamp: string
  alert_level: AlertLevel
}

// ── WebSocket Messages ────────────────────────────────────────────────────────

export interface WsMessage {
  type: 'network_update' | 'connected' | 'heartbeat' | 'scenario_changed' | 'network_changed' | 'error'
  tick?: number
  timestamp?: number
  network?: NetworkSnapshot
  leak_analysis?: LeakReport
  system?: SystemStatus
  message?: string
  scenario?: string
  city?: string
  success?: boolean
}

export interface SystemStatus {
  health: number
  scenario: Scenario
  total_demand: number
  total_leakage: number
}

// ── Reports ───────────────────────────────────────────────────────────────────

export interface ReportResponse {
  report: string
  language: Language
  provider: 'groq' | 'openai' | 'template'
  leak_data: LeakReport
  generated_at: string
}

// ── History ───────────────────────────────────────────────────────────────────

export interface HistoryEvent extends LeakReport {
  recorded_at: string
}

export interface HistoryResponse {
  total: number
  events: HistoryEvent[]
}

// ── IoT Nodes (Phase 2) ───────────────────────────────────────────────────────

export interface IoTNode {
  node_id: string
  name: string
  device_type: 'simulated' | 'esp32' | 'lora'
  battery_level: number
  rssi: number
  pressure: number
  status: NodeStatus
  last_seen: string
  firmware_version: string
  latitude: number | null
  longitude: number | null
}

// ── UI State ──────────────────────────────────────────────────────────────────

export interface DashboardState {
  network: NetworkSnapshot | null
  leakReport: LeakReport | null
  isConnected: boolean
  scenario: Scenario
  lastUpdate: Date | null
  history: HistoryEvent[]
}

export interface PressureDataPoint {
  time: string
  [nodeId: string]: string | number
}
