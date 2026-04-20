"use client";

import { createContext, type ReactNode, useCallback, useContext, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import type { User } from "./user";

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  loginWithSSO: () => Promise<void>;
  logout: () => Promise<void>;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();
  const hasConfiguredClient = useRef(false);

  /**
   * Configure the apiClient's onUnauthorized callback so it can
   * trigger logout redirect when a 401 is received. We use a ref-based
   * pattern so the callback is always up-to-date without reconfiguring
   * the client on every render.
   */
  useEffect(() => {
    if (hasConfiguredClient.current) return;
    hasConfiguredClient.current = true;

    // Lazy import to avoid circular dependency issues
    import("@/lib/api/client").then(({ apiClient }) => {
      apiClient.configure({
        onUnauthorized: () => {
          // Clear local state and redirect to login
          setUser(null);
          localStorage.removeItem("user");
          const currentPath = window.location.pathname;
          const loginUrl = currentPath !== "/login"
            ? `/login?redirect=${encodeURIComponent(currentPath)}`
            : "/login";
          router.push(loginUrl);
        },
      });
    });
  }, [router]);

  useEffect(() => {
    const checkAuth = async () => {
      try {
        // Always use absolute /api/v1 path (proxied through nginx)
        const response = await fetch("/api/v1/auth/me");
        if (response.ok) {
          const userData = await response.json();
          const user: User = {
            id: userData.sub || "1",
            email: userData.username || "",
            name: userData.username || "Demo User",
            role: userData.role || "admin",
          };
          setUser(user);
          localStorage.setItem("user", JSON.stringify(user));
        } else {
          // Not authenticated, check localStorage fallback
          const storedUser = localStorage.getItem("user");
          if (storedUser) {
            setUser(JSON.parse(storedUser));
          }
        }
      } catch (error) {
        console.error("[auth] Auth check failed:", error);
      } finally {
        setIsLoading(false);
      }
    };
    checkAuth();
  }, []);

  const login = async (email: string, password: string) => {
    setIsLoading(true);
    try {
      const response = await fetch("/api/v1/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: email, password }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Login failed");
      }

      const data = await response.json();
      // data: { access_token, refresh_token, token_type }

      // Store tokens in the apiClient so all subsequent API calls are authenticated
      const { apiClient } = await import("@/lib/api/client");
      apiClient.configure({
        token: data.access_token,
        refreshToken: data.refresh_token,
      });

      // Fetch user info
      const meResponse = await fetch("/api/v1/auth/me", {
        headers: { Authorization: `Bearer ${data.access_token}` },
      });

      if (meResponse.ok) {
        const meData = await meResponse.json();
        const user: User = {
          id: meData.sub || "1",
          email: meData.username || email,
          name: meData.username || "Demo User",
          role: meData.role || "admin",
        };
        setUser(user);
        localStorage.setItem("user", JSON.stringify(user));
      } else {
        // Fallback: construct user from token
        const mockUser: User = {
          id: "1",
          email: email,
          name: email,
          role: "admin",
          avatar: `https://api.dicebear.com/7.x/avataaars/svg?seed=${email}`,
        };
        setUser(mockUser);
        localStorage.setItem("user", JSON.stringify(mockUser));
      }
    } finally {
      setIsLoading(false);
    }
  };

  const loginWithSSO = async () => {
    const currentPath = window.location.pathname;
    window.location.href = `/api/v1/auth/login?redirect=${encodeURIComponent(currentPath)}`;
  };

  const logout = async () => {
    try {
      // Send the refresh token to the backend so it can be revoked
      const { apiClient } = await import("@/lib/api/client");
      const refreshToken = apiClient.getConfig().refreshToken;
      if (refreshToken) {
        await fetch("/api/v1/auth/logout", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
      } else {
        await fetch("/api/v1/auth/logout", { method: "POST" });
      }
      // Clear the apiClient tokens
      apiClient.configure({ token: undefined, refreshToken: undefined });
    } catch (error) {
      console.error("[auth] Logout failed:", error);
    }
    setUser(null);
    localStorage.removeItem("user");
    router.push("/login");
  };

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
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
