/**
 * useWebSocket — Real-time connection to Maayan backend.
 * Handles reconnection, heartbeats, and message dispatching.
 */

import { useEffect, useRef, useState, useCallback } from 'react'
import { WsMessage, NetworkSnapshot, LeakReport } from '../types'
import { getToken } from '../lib/auth'

function buildWsUrl(token: string | null): string {
  const base = import.meta.env.VITE_WS_URL
    ? `${import.meta.env.VITE_WS_URL}/ws`
    : 'ws://localhost:8000/ws'
  if (!token) return base
  const sep = base.includes('?') ? '&' : '?'
  return `${base}${sep}token=${encodeURIComponent(token)}`
}

const RECONNECT_DELAY = 3000
const MAX_RECONNECT_ATTEMPTS = 10

interface UseWebSocketReturn {
  isConnected: boolean
  network: NetworkSnapshot | null
  leakReport: LeakReport | null
  lastTick: number
  sendMessage: (msg: object) => void
  connectionAttempt: number
}

export function useWebSocket(enabled = true): UseWebSocketReturn {
  const ws = useRef<WebSocket | null>(null)
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout>>()
  const attemptCount = useRef(0)

  const [isConnected, setIsConnected] = useState(false)
  const [network, setNetwork] = useState<NetworkSnapshot | null>(null)
  const [leakReport, setLeakReport] = useState<LeakReport | null>(null)
  const [lastTick, setLastTick] = useState(0)
  const [connectionAttempt, setConnectionAttempt] = useState(0)

  const handleMessage = useCallback((msg: WsMessage) => {
    switch (msg.type) {
      case 'network_update':
        if (msg.network) setNetwork(msg.network)
        if (msg.leak_analysis) setLeakReport(msg.leak_analysis)
        if (msg.tick) setLastTick(msg.tick)
        break
      case 'connected':
        if (msg.network) setNetwork(msg.network)
        if (msg.leak_analysis) setLeakReport(msg.leak_analysis)
        break
      case 'heartbeat':
        break
      case 'scenario_changed':
      case 'network_changed':
        break
    }
  }, [])

  const connect = useCallback(() => {
    if (!enabled) return
    if (ws.current?.readyState === WebSocket.OPEN) return

    const token = getToken()
    if (!token) return

    try {
      const socket = new WebSocket(buildWsUrl(token))
      ws.current = socket

      socket.onopen = () => {
        setIsConnected(true)
        attemptCount.current = 0
        setConnectionAttempt(0)
      }

      socket.onmessage = (event) => {
        try {
          const msg: WsMessage = JSON.parse(event.data)
          handleMessage(msg)
        } catch (e) {
          console.warn('WS parse error:', e)
        }
      }

      socket.onclose = () => {
        setIsConnected(false)
        ws.current = null
        if (enabled && getToken()) scheduleReconnect()
      }

      socket.onerror = () => {
        socket.close()
      }
    } catch {
      scheduleReconnect()
    }
  }, [enabled, handleMessage])

  const scheduleReconnect = useCallback(() => {
    if (!enabled || !getToken()) return
    if (attemptCount.current >= MAX_RECONNECT_ATTEMPTS) return
    attemptCount.current++
    setConnectionAttempt(attemptCount.current)

    clearTimeout(reconnectTimeout.current)
    reconnectTimeout.current = setTimeout(() => {
      connect()
    }, RECONNECT_DELAY * Math.min(attemptCount.current, 3))
  }, [connect, enabled])

  const sendMessage = useCallback((msg: object) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(msg))
    }
  }, [])

  useEffect(() => {
    if (!enabled) {
      ws.current?.close()
      setIsConnected(false)
      return
    }
    connect()
    return () => {
      clearTimeout(reconnectTimeout.current)
      ws.current?.close()
    }
  }, [connect, enabled])

  return { isConnected, network, leakReport, lastTick, sendMessage, connectionAttempt }
}
