/**
 * Auth token storage and helpers.
 */

const TOKEN_KEY = 'maayan_auth_token'
const USER_KEY = 'maayan_auth_user'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string, username: string): void {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, username)
}

export function clearAuth(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

export function getStoredUsername(): string | null {
  return localStorage.getItem(USER_KEY)
}

export function isAuthenticated(): boolean {
  return Boolean(getToken())
}
