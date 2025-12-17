// useRealtime - Hook for real-time updates via Server-Sent Events
// Provides connection management, auto-reconnection, and typed event handling

import { useState, useEffect, useCallback, useRef } from 'react';

// ============ Types ============

export interface RealtimeEvent<T = unknown> {
    type: string;
    data: T;
    timestamp: string;
    id?: string;
}

export interface ProtocolStatusEvent {
    protocol_id: number;
    status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
    current_step?: string;
    progress?: number;
}

export interface StepStatusEvent {
    protocol_id: number;
    step_id: number;
    status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
    output?: string;
    error?: string;
}

export interface QualityCheckEvent {
    protocol_id: number;
    gate_name: string;
    status: 'passed' | 'warning' | 'failed';
    findings?: string[];
}

export interface ClarificationEvent {
    protocol_id: number;
    clarification_id: number;
    question: string;
    blocking: boolean;
}

export interface ConnectionStatus {
    connected: boolean;
    reconnecting: boolean;
    error: string | null;
    lastEventTime: string | null;
}

interface UseRealtimeOptions {
    url?: string;
    autoConnect?: boolean;
    reconnectDelay?: number;
    maxReconnectAttempts?: number;
}

type EventHandler = (event: RealtimeEvent) => void;

// ============ useRealtime Hook ============

export function useRealtime(options: UseRealtimeOptions = {}) {
    const {
        url = '/api/events',
        reconnectDelay = 3000,
        maxReconnectAttempts = 5,
    } = options;

    const autoConnect = options.autoConnect ?? true;

    const [status, setStatus] = useState<ConnectionStatus>({
        connected: false,
        reconnecting: false,
        error: null,
        lastEventTime: null,
    });

    const eventSourceRef = useRef<EventSource | null>(null);
    const reconnectAttempts = useRef(0);
    const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const handlersRef = useRef<Map<string, Set<EventHandler>>>(new Map());

    // Connect to SSE endpoint
    const connect = useCallback(() => {
        if (eventSourceRef.current?.readyState === EventSource.OPEN) {
            return; // Already connected
        }

        try {
            const eventSource = new EventSource(url);
            eventSourceRef.current = eventSource;

            eventSource.onopen = () => {
                setStatus(prev => ({
                    ...prev,
                    connected: true,
                    reconnecting: false,
                    error: null,
                }));
                reconnectAttempts.current = 0;
            };

            eventSource.onerror = () => {
                setStatus(prev => ({
                    ...prev,
                    connected: false,
                    error: 'Connection lost',
                }));

                eventSource.close();
                eventSourceRef.current = null;

                // Try to reconnect
                if (reconnectAttempts.current < maxReconnectAttempts) {
                    reconnectAttempts.current += 1;
                    setStatus(prev => ({ ...prev, reconnecting: true }));

                    reconnectTimeoutRef.current = setTimeout(() => {
                        connect();
                    }, reconnectDelay);
                } else {
                    setStatus(prev => ({
                        ...prev,
                        reconnecting: false,
                        error: 'Max reconnection attempts reached',
                    }));
                }
            };

            eventSource.onmessage = (event) => {
                try {
                    const parsed: RealtimeEvent = JSON.parse(event.data);

                    setStatus(prev => ({
                        ...prev,
                        lastEventTime: parsed.timestamp || new Date().toISOString(),
                    }));

                    // Dispatch to type-specific handlers
                    const handlers = handlersRef.current.get(parsed.type);
                    if (handlers) {
                        handlers.forEach(handler => handler(parsed));
                    }

                    // Dispatch to wildcard handlers
                    const wildcardHandlers = handlersRef.current.get('*');
                    if (wildcardHandlers) {
                        wildcardHandlers.forEach(handler => handler(parsed));
                    }
                } catch (e) {
                    console.error('Failed to parse SSE event:', e);
                }
            };
        } catch (e) {
            setStatus(prev => ({
                ...prev,
                connected: false,
                error: e instanceof Error ? e.message : 'Connection failed',
            }));
        }
    }, [url, reconnectDelay, maxReconnectAttempts]);

    // Disconnect from SSE
    const disconnect = useCallback(() => {
        if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current);
            reconnectTimeoutRef.current = null;
        }

        if (eventSourceRef.current) {
            eventSourceRef.current.close();
            eventSourceRef.current = null;
        }

        setStatus({
            connected: false,
            reconnecting: false,
            error: null,
            lastEventTime: null,
        });
        reconnectAttempts.current = 0;
    }, []);

    // Subscribe to specific event type (using trailing comma to disambiguate from JSX)
    const subscribe = useCallback(<T,>(eventType: string, handler: (event: RealtimeEvent<T>) => void) => {
        if (!handlersRef.current.has(eventType)) {
            handlersRef.current.set(eventType, new Set());
        }
        handlersRef.current.get(eventType)!.add(handler as EventHandler);

        // Return unsubscribe function
        return () => {
            const handlers = handlersRef.current.get(eventType);
            if (handlers) {
                handlers.delete(handler as EventHandler);
                if (handlers.size === 0) {
                    handlersRef.current.delete(eventType);
                }
            }
        };
    }, []);

    // Auto-connect on mount
    useEffect(() => {
        if (autoConnect) {
            connect();
        }
        return () => {
            disconnect();
        };
    }, [autoConnect, connect, disconnect]);

    return {
        status,
        connect,
        disconnect,
        subscribe,
    };
}

// ============ useProtocolRealtime Hook ============

interface UseProtocolRealtimeOptions {
    protocolId: number;
    onStatusChange?: (event: ProtocolStatusEvent) => void;
    onStepUpdate?: (event: StepStatusEvent) => void;
    onQualityCheck?: (event: QualityCheckEvent) => void;
    onClarification?: (event: ClarificationEvent) => void;
}

export function useProtocolRealtime({
    protocolId,
    onStatusChange,
    onStepUpdate,
    onQualityCheck,
    onClarification,
}: UseProtocolRealtimeOptions) {
    const { status, connect, disconnect, subscribe } = useRealtime({
        url: `/api/protocols/${protocolId}/events`,
    });

    useEffect(() => {
        const unsubscribers: Array<() => void> = [];

        if (onStatusChange) {
            unsubscribers.push(
                subscribe<ProtocolStatusEvent>('protocol.status', (event) => {
                    if (event.data.protocol_id === protocolId) {
                        onStatusChange(event.data);
                    }
                })
            );
        }

        if (onStepUpdate) {
            unsubscribers.push(
                subscribe<StepStatusEvent>('step.update', (event) => {
                    if (event.data.protocol_id === protocolId) {
                        onStepUpdate(event.data);
                    }
                })
            );
        }

        if (onQualityCheck) {
            unsubscribers.push(
                subscribe<QualityCheckEvent>('quality.check', (event) => {
                    if (event.data.protocol_id === protocolId) {
                        onQualityCheck(event.data);
                    }
                })
            );
        }

        if (onClarification) {
            unsubscribers.push(
                subscribe<ClarificationEvent>('clarification.created', (event) => {
                    if (event.data.protocol_id === protocolId) {
                        onClarification(event.data);
                    }
                })
            );
        }

        return () => {
            unsubscribers.forEach(unsub => unsub());
        };
    }, [protocolId, onStatusChange, onStepUpdate, onQualityCheck, onClarification, subscribe]);

    return { status, connect, disconnect };
}

// ============ Connection Status Indicator ============

interface ConnectionIndicatorProps {
    status: ConnectionStatus;
    className?: string;
}

export function ConnectionIndicator({ status, className = '' }: ConnectionIndicatorProps) {
    let statusClass = 'disconnected';
    let statusText = 'Disconnected';
    let statusIcon = '🔴';

    if (status.connected) {
        statusClass = 'connected';
        statusText = 'Connected';
        statusIcon = '🟢';
    } else if (status.reconnecting) {
        statusClass = 'reconnecting';
        statusText = 'Reconnecting...';
        statusIcon = '🟡';
    }

    return (
        <span className={`connection-indicator connection-${statusClass} ${className}`}>
            <span className="connection-icon">{statusIcon}</span>
            <span className="connection-text">{statusText}</span>
        </span>
    );
}

export default useRealtime;
