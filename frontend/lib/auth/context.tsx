"use client"

import { createContext, useContext, type ReactNode, useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import type { User } from "./user"

interface AuthContextType {
  user: User | null
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  loginWithSSO: () => Promise<void>
  logout: () => Promise<void>
  isAuthenticated: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const router = useRouter()
  const basePath =
    process.env.NEXT_PUBLIC_BASE_PATH ||
    (typeof window !== "undefined" && window.location.pathname.startsWith("/console") ? "/console" : "")

  useEffect(() => {
    const checkAuth = async () => {
      try {
        const response = await fetch(`${basePath}/api/auth/me`)
        if (response.ok) {
          const userData = await response.json()
          setUser(userData)
        } else {
          // Not authenticated, check localStorage fallback
          const storedUser = localStorage.getItem("user")
          if (storedUser) {
            setUser(JSON.parse(storedUser))
          }
        }
      } catch (error) {
        console.error("[v0] Auth check failed:", error)
      } finally {
        setIsLoading(false)
      }
    }
    checkAuth()
    // </CHANGE>
  }, [basePath])

  const login = async (email: string, _password: string) => {
    setIsLoading(true)
    try {
      // Mock email/password login
      const mockUser: User = {
        id: "1",
        email: email,
        name: "Demo User",
        role: "admin",
        avatar: `https://api.dicebear.com/7.x/avataaars/svg?seed=${email}`,
      }
      setUser(mockUser)
      localStorage.setItem("user", JSON.stringify(mockUser))
    } finally {
      setIsLoading(false)
    }
  }

  const loginWithSSO = async () => {
    const currentPath = window.location.pathname
    window.location.href = `${basePath}/api/auth/login?redirect=${encodeURIComponent(currentPath)}`
  }
  // </CHANGE>

  const logout = async () => {
    try {
      await fetch(`${basePath}/api/auth/logout`, { method: "POST" })
    } catch (error) {
      console.error("[v0] Logout failed:", error)
    }
    // </CHANGE>
    setUser(null)
    localStorage.removeItem("user")
    router.push("/login")
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        login,
        loginWithSSO,
        logout,
        isAuthenticated: !!user,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}
