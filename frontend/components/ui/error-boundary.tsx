"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";

import { AlertCircle, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onReset?: () => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("ErrorBoundary caught an error:", error, errorInfo);
    this.setState({ errorInfo });
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
    this.props.onReset?.();
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <Card className="border-destructive m-4">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-destructive">
              <AlertCircle className="h-5 w-5" />
              Something went wrong
            </CardTitle>
            <CardDescription>
              An unexpected error occurred while rendering this component.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {this.state.error && (
              <div className="bg-destructive/10 rounded-md p-3">
                <p className="text-destructive font-mono text-sm">
                  {this.state.error.message}
                </p>
              </div>
            )}
            <div className="flex gap-2">
              <Button onClick={this.handleReset} variant="default">
                <RefreshCw className="mr-2 h-4 w-4" />
                Try Again
              </Button>
              <Button onClick={() => window.location.reload()} variant="outline">
                Reload Page
              </Button>
            </div>
          </CardContent>
        </Card>
      );
    }

    return this.props.children;
  }
}

/**
 * Lightweight error fallback for inline errors.
 * Use this for smaller components like cards, lists, etc.
 */
interface InlineErrorProps {
  message?: string;
  onRetry?: () => void;
  className?: string;
}

export function InlineError({ 
  message = "Failed to load", 
  onRetry,
  className 
}: InlineErrorProps) {
  return (
    <div className={`flex items-center justify-center gap-2 py-4 ${className || ""}`}>
      <AlertCircle className="text-destructive h-4 w-4" />
      <span className="text-muted-foreground text-sm">{message}</span>
      {onRetry && (
        <Button onClick={onRetry} variant="ghost" size="sm">
          <RefreshCw className="h-3 w-3" />
        </Button>
      )}
    </div>
  );
}

/**
 * Query error fallback - shows when a React Query fails.
 */
interface QueryErrorProps {
  error: unknown;
  onRetry?: () => void;
  className?: string;
}

export function QueryError({ error, onRetry, className: _className }: QueryErrorProps) {
  const message = error instanceof Error ? error.message : "An error occurred while fetching data";
  
  return (
    <Card className="border-destructive/50 m-4">
      <CardContent className="flex items-center justify-between py-4">
        <div className="flex items-center gap-2">
          <AlertCircle className="text-destructive h-4 w-4" />
          <span className="text-sm">{message}</span>
        </div>
        {onRetry && (
          <Button onClick={onRetry} variant="outline" size="sm">
            <RefreshCw className="mr-2 h-3 w-3" />
            Retry
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
