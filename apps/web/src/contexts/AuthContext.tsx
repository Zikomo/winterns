import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { api } from '@/lib/api'
import { setToken, clearToken, isAuthenticated as checkTokenValid } from '@/lib/auth'
import type { User } from '@/types'

export interface AuthContextValue {
  user: User | null
  isLoading: boolean
  isAuthenticated: boolean
  /** True when user fetch failed with a transient error (network, 5xx) */
  authError: boolean
  login: (token: string) => Promise<void>
  logout: () => void
  /** Retry fetching user after a transient error */
  retryAuth: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)

interface AuthProviderProps {
  children: ReactNode
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [authError, setAuthError] = useState(false)

  const fetchUser = useCallback(async () => {
    if (!checkTokenValid()) {
      setUser(null)
      setAuthError(false)
      setIsLoading(false)
      return
    }

    try {
      const response = await api.get<User>('/auth/users/me')
      setUser(response.data)
      setAuthError(false)
    } catch (error) {
      // Only clear token on auth failures (401/403), not transient errors
      const status = (error as { response?: { status: number } })?.response?.status
      if (status === 401 || status === 403) {
        clearToken()
        setUser(null)
        setAuthError(false)
      } else {
        // For other errors (network, 5xx), keep token and mark error for retry
        setAuthError(true)
      }
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchUser()
  }, [fetchUser])

  const login = useCallback(async (token: string) => {
    setToken(token)
    setIsLoading(true)
    await fetchUser()
  }, [fetchUser])

  const logout = useCallback(() => {
    clearToken()
    setUser(null)
    setAuthError(false)
  }, [])

  const retryAuth = useCallback(async () => {
    setIsLoading(true)
    setAuthError(false)
    await fetchUser()
  }, [fetchUser])

  // Use token validity for isAuthenticated, not user object.
  // This prevents redirect loops when user fetch fails with transient errors.
  const isAuthenticatedValue = checkTokenValid()

  const value = useMemo(
    () => ({
      user,
      isLoading,
      isAuthenticated: isAuthenticatedValue,
      authError,
      login,
      logout,
      retryAuth,
    }),
    [user, isLoading, isAuthenticatedValue, authError, login, logout, retryAuth]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
