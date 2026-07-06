/**
 * useApi — HTTP API client hooks for Maayan backend.
 */

import { useState, useCallback } from 'react'
import { Scenario, Language, ReportResponse, HistoryResponse, NetworkListResponse } from '../types'
import { getToken, clearAuth } from '../lib/auth'

const API_BASE = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/api`
  : 'http://localhost:8000/api'

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getToken()
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
    ...options,
  })
  if (response.status === 401) {
    clearAuth()
    window.location.href = '/login'
    throw new Error('Session expired')
  }
  if (!response.ok) {
    const error = await response.text()
    throw new Error(`API ${response.status}: ${error}`)
  }
  return response.json()
}

export function useScenario() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const setScenario = useCallback(async (scenario: Scenario) => {
    setLoading(true)
    setError(null)
    try {
      await apiFetch('/scenario', {
        method: 'POST',
        body: JSON.stringify({ scenario }),
      })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to set scenario')
    } finally {
      setLoading(false)
    }
  }, [])

  return { setScenario, loading, error }
}

export function useNetworks() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [networks, setNetworks] = useState<NetworkListResponse | null>(null)

  const fetchNetworks = useCallback(async () => {
    try {
      const data = await apiFetch<NetworkListResponse>('/networks')
      setNetworks(data)
      return data
    } catch (e) {
      console.error('Networks fetch error:', e)
      return null
    }
  }, [])

  const selectNetwork = useCallback(async (city: string) => {
    setLoading(true)
    setError(null)
    try {
      await apiFetch('/networks/select', {
        method: 'POST',
        body: JSON.stringify({ city }),
      })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to switch network')
    } finally {
      setLoading(false)
    }
  }, [])

  return { fetchNetworks, selectNetwork, networks, loading, error }
}

export function useReport() {
  const [loading, setLoading] = useState(false)
  const [report, setReport] = useState<ReportResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const fetchReport = useCallback(async (language: Language = 'en', context?: string) => {
    setLoading(true)
    setError(null)
    try {
      const data = await apiFetch<ReportResponse>('/report', {
        method: 'POST',
        body: JSON.stringify({ language, context }),
      })
      setReport(data)
      return data
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to generate report')
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  return { fetchReport, report, loading, error }
}

export function useHistory() {
  const [loading, setLoading] = useState(false)
  const [history, setHistory] = useState<HistoryResponse | null>(null)

  const fetchHistory = useCallback(async (limit = 50, severity?: string) => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ limit: String(limit) })
      if (severity) params.set('severity', severity)
      const data = await apiFetch<HistoryResponse>(`/history?${params}`)
      setHistory(data)
      return data
    } catch (e) {
      console.error('History fetch error:', e)
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  const clearHistory = useCallback(async () => {
    await apiFetch('/history', { method: 'DELETE' })
    setHistory(null)
  }, [])

  return { fetchHistory, clearHistory, history, loading }
}

export function useIoTNodes() {
  const [loading, setLoading] = useState(false)
  const [nodes, setNodes] = useState<unknown[]>([])
  const [liveCount, setLiveCount] = useState(0)

  const fetchNodes = useCallback(async () => {
    setLoading(true)
    try {
      const data = await apiFetch<{ nodes: unknown[]; live_count?: number }>('/iot/nodes')
      setNodes(data.nodes)
      setLiveCount(data.live_count ?? 0)
    } catch (e) {
      console.error('IoT nodes error:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  return { fetchNodes, nodes, liveCount, loading }
}

export interface MlLearningStatus {
  enabled: boolean
  retraining: boolean
  total_recorded: number
  samples_since_retrain: number
  retrain_threshold: number
  last_retrain_at: string | null
  last_retrain_metrics?: {
    samples?: number
    severity_accuracy?: number
    localization_mae?: number | null
  }
  sample_counts?: {
    baseline: number
    continuous: number
    feedback: number
    combined: number
  }
}

export function useMlStatus() {
  const [status, setStatus] = useState<MlLearningStatus | null>(null)
  const [loading, setLoading] = useState(false)

  const fetchStatus = useCallback(async () => {
    setLoading(true)
    try {
      const data = await apiFetch<MlLearningStatus>('/ml/status')
      setStatus(data)
      return data
    } catch (e) {
      console.error('ML status error:', e)
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  const triggerRetrain = useCallback(async () => {
    await apiFetch('/ml/retrain', { method: 'POST' })
    return fetchStatus()
  }, [fetchStatus])

  return { status, fetchStatus, triggerRetrain, loading }
}
