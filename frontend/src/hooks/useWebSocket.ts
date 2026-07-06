/**
 * useWebSocket — Real-time connection to Maayan backend.
 * Handles reconnection, heartbeats, and message dispatching.
 */

import { useEffect, useRef, useState, useCallback } from 'react'
import { WsMessage, NetworkSnapshot, LeakReport } from '../types'

const WS_URL = import.meta.env.VITE_WS_URL
  ? `${import.meta.env.VITE_WS_URL}/ws`
  : 'ws://localhost:8000/ws'

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

export function useWebSocket(): UseWebSocketReturn {
  const ws = useRef<WebSocket | null>(null)
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout>>()
  const attemptCount = useRef(0)

  const [isConnected, setIsConnected] = useState(false)
  const [network, setNetwork] = useState<NetworkSnapshot | null>(null)
  const [leakReport, setLeakReport] = useState<LeakReport | null>(null)
  const [lastTick, setLastTick] = useState(0)
  const [connectionAttempt, setConnectionAttempt] = useState(0)

  const connect = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) return

    try {
      const socket = new WebSocket(WS_URL)
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
        scheduleReconnect()
      }

      socket.onerror = () => {
        socket.close()
      }
    } catch (e) {
      scheduleReconnect()
    }
  }, [])

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
        // Keep-alive, no action needed
        break
      case 'scenario_changed':
      case 'network_changed':
        // Reflected on the next network_update broadcast tick
        break
    }
  }, [])

  const scheduleReconnect = useCallback(() => {
    if (attemptCount.current >= MAX_RECONNECT_ATTEMPTS) return
    attemptCount.current++
    setConnectionAttempt(attemptCount.current)

    clearTimeout(reconnectTimeout.current)
    reconnectTimeout.current = setTimeout(() => {
      connect()
    }, RECONNECT_DELAY * Math.min(attemptCount.current, 3))
  }, [connect])

  const sendMessage = useCallback((msg: object) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(msg))
    }
  }, [])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectTimeout.current)
      ws.current?.close()
    }
  }, [connect])

  return { isConnected, network, leakReport, lastTick, sendMessage, connectionAttempt }
}
