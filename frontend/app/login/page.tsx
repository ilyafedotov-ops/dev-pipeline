"use client"

import type React from "react"

import { useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Layers } from "lucide-react"
import { useAuth } from "@/lib/auth/context"
import { toast } from "sonner"

export default function LoginPage() {
  const [email, setEmail] = useState("demo@tasksgodzilla.dev")
  const [password, setPassword] = useState("demo")
  const [isLoading, setIsLoading] = useState(false)
  const router = useRouter()
  const searchParams = useSearchParams()
  const { login, loginWithSSO } = useAuth()
  const redirect = searchParams.get("redirect") || "/projects"

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)

    try {
      await login(email, password)
      toast.success("Successfully logged in")
      router.push(redirect)
    } catch {
      toast.error("Login failed. Please try again.")
    } finally {
      setIsLoading(false)
    }
  }

  const handleSSOLogin = async () => {
    setIsLoading(true)
    try {
      await loginWithSSO()
    } catch {
      toast.error("SSO login failed")
      setIsLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-background to-muted p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-4 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-lg bg-primary">
            <Layers className="h-7 w-7 text-primary-foreground" />
          </div>
          <CardTitle className="text-2xl">Welcome to TasksGodzilla</CardTitle>
          <CardDescription>Sign in to access the control console</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="demo@tasksgodzilla.dev"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? "Signing in..." : "Sign in"}
            </Button>
          </form>
          <div className="mt-6 space-y-4">
            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <span className="w-full border-t" />
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-card px-2 text-muted-foreground">Or continue with</span>
              </div>
            </div>
            <Button
              variant="outline"
              className="w-full bg-transparent"
              type="button"
              onClick={handleSSOLogin}
              disabled={isLoading}
            >
              SSO / OIDC
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
