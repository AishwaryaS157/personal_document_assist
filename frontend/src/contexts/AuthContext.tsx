import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import { login as apiLogin, register as apiRegister, logout as apiLogout, getMe } from '../api/client'

interface AuthState {
  session: { email: string } | null
  email: string | null
  loading: boolean
}

interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ session: null, email: null, loading: true })

  useEffect(() => {
    getMe()
      .then((email) => setState({ session: { email }, email, loading: false }))
      .catch(() => setState({ session: null, email: null, loading: false }))
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const user = await apiLogin(email, password)
    setState({ session: { email: user.email }, email: user.email, loading: false })
  }, [])

  const register = useCallback(async (email: string, password: string) => {
    const user = await apiRegister(email, password)
    setState({ session: { email: user.email }, email: user.email, loading: false })
  }, [])

  const logout = useCallback(async () => {
    await apiLogout()
    setState({ session: null, email: null, loading: false })
  }, [])

  return (
    <AuthContext.Provider value={{ ...state, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
