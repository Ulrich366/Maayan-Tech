/**
 * useApi — HTTP API client hooks for Maayan backend.
 */

import { useState, useCallback } from 'react'
import { Scenario, Language, ReportResponse, HistoryResponse } from '../types'

const API_BASE = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/api`
  : 'http://localhost:8000/api'

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
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

  const fetchNodes = useCallback(async () => {
    setLoading(true)
    try {
      const data = await apiFetch<{ nodes: unknown[] }>('/iot/nodes')
      setNodes(data.nodes)
    } catch (e) {
      console.error('IoT nodes error:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  return { fetchNodes, nodes, loading }
}
