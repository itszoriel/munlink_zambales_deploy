import { create } from 'zustand'

export type User = {
  id: number
  username: string
  email: string
  first_name: string
  middle_name?: string
  last_name: string
  role: string
  admin_municipality_id?: number
  profile_picture?: string
  email_verified: boolean
  admin_verified: boolean
  municipality_name?: string
  municipality_slug?: string
  admin_municipality_name?: string
  admin_municipality_slug?: string
}

type AdminState = {
  user?: User
  accessToken?: string
  refreshToken?: string
  isAuthenticated: boolean
  setAuth: (user: User, accessToken: string, refreshToken: string) => void
  setTokens: (accessToken: string, refreshToken?: string) => void
  logout: () => void
  updateUser: (user: User) => void
}

export const useAdminStore = create<AdminState>((set) => {
  // Load from localStorage on init
  const storedToken = typeof window !== 'undefined' ? localStorage.getItem('admin:access_token') : null
  const storedRefreshToken = typeof window !== 'undefined' ? localStorage.getItem('admin:refresh_token') : null
  const storedUser = typeof window !== 'undefined' ? localStorage.getItem('admin:user') : null
  
  let initialUser: User | undefined
  try {
    initialUser = storedUser ? JSON.parse(storedUser) : undefined
  } catch {
    initialUser = undefined
  }

  return {
    user: initialUser,
    accessToken: storedToken || undefined,
    refreshToken: storedRefreshToken || undefined,
    isAuthenticated: !!storedToken && !!initialUser,
    setAuth: (user, accessToken, refreshToken) => {
      if (typeof window !== 'undefined') {
        localStorage.setItem('admin:access_token', accessToken)
        localStorage.setItem('admin:refresh_token', refreshToken)
        localStorage.setItem('admin:user', JSON.stringify(user))
      }
      set({ user, accessToken, refreshToken, isAuthenticated: true })
    },
    setTokens: (accessToken, refreshToken) => {
      if (typeof window !== 'undefined') {
        localStorage.setItem('admin:access_token', accessToken)
        if (refreshToken) {
          localStorage.setItem('admin:refresh_token', refreshToken)
        }
      }
      set((state) => ({
        accessToken,
        refreshToken: refreshToken ?? state.refreshToken,
        isAuthenticated: !!accessToken && !!state.user,
      }))
    },
    logout: () => {
      if (typeof window !== 'undefined') {
        localStorage.removeItem('admin:access_token')
        localStorage.removeItem('admin:refresh_token')
        localStorage.removeItem('admin:user')
        try { sessionStorage.clear() } catch {}
      }
      set({ user: undefined, accessToken: undefined, refreshToken: undefined, isAuthenticated: false })
    },
    updateUser: (user) => {
      if (typeof window !== 'undefined') {
        localStorage.setItem('admin:user', JSON.stringify(user))
      }
      set({ user })
    },
  }
})

