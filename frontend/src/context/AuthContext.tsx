import { createContext, useContext, useState, useCallback, useEffect, ReactNode } from 'react'
import { getToken, setToken, clearAuth, getStoredUsername } from '../lib/auth'

const API_BASE = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/api`
  : 'http://localhost:8000/api'

interface AuthContextValue {
  token: string | null
  username: string | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState<string | null>(() => getToken())
  const [username, setUsername] = useState<string | null>(() => getStoredUsername())
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    setTokenState(getToken())
    setUsername(getStoredUsername())
    setIsLoading(false)
  }, [])

  const login = useCallback(async (user: string, password: string) => {
    const response = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: user, password }),
    })

    if (!response.ok) {
      const detail = await response.text()
      throw new Error(detail.includes('Invalid') ? 'Invalid username or password' : 'Login failed')
    }

    const data = await response.json()
    setToken(data.access_token, data.username)
    setTokenState(data.access_token)
    setUsername(data.username)
  }, [])

  const logout = useCallback(() => {
    clearAuth()
    setTokenState(null)
    setUsername(null)
    window.location.href = '/login'
  }, [])

  return (
    <AuthContext.Provider
      value={{
        token,
        username,
        isAuthenticated: Boolean(token),
        isLoading,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
