/**
 * Resolve API / WebSocket base URLs for dev and production.
 * Guards against invalid baked-in placeholders (e.g. Railway template leaks).
 */

const PRODUCTION_API = 'https://backend-production-357a.up.railway.app'
const LOCAL_API = 'http://localhost:8000'

function sanitizeRoot(url: string | undefined): string | null {
  if (!url) return null
  const trimmed = url.trim().replace(/\/$/, '')
  if (!trimmed || trimmed.includes('<') || trimmed.includes('>')) return null
  try {
    // eslint-disable-next-line no-new
    new URL(trimmed)
    return trimmed
  } catch {
    return null
  }
}

export function getApiRoot(): string {
  return (
    sanitizeRoot(import.meta.env.VITE_API_URL) ??
    (import.meta.env.PROD ? PRODUCTION_API : LOCAL_API)
  )
}

export function getApiBase(): string {
  return `${getApiRoot()}/api`
}

export function getWsUrl(): string {
  const wsRoot = sanitizeRoot(import.meta.env.VITE_WS_URL)
  if (wsRoot) return `${wsRoot}/ws`

  const apiRoot = getApiRoot()
  if (apiRoot.startsWith('https://')) return `${apiRoot.replace(/^https/, 'wss')}/ws`
  if (apiRoot.startsWith('http://')) return `${apiRoot.replace(/^http/, 'ws')}/ws`
  return 'ws://localhost:8000/ws'
}
