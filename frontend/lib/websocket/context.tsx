"use client";

import {
  createContext,
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { apiClient } from "@/lib/api/client";

import type {
  ConnectionState,
  WebSocketClientMessage,
  WebSocketServerMessage,
  WebSocketStatus,
} from "./types";

type WebSocketListener = (message: WebSocketServerMessage) => void;

export type WebSocketContextValue = {
  status: WebSocketStatus;
  connectionState: ConnectionState;
  lastMessage: WebSocketServerMessage | null;
  isConnected: boolean;
  connect: () => void;
  disconnect: () => void;
  sendJson: (message: WebSocketClientMessage) => void;
  send: (message: WebSocketClientMessage) => void;
  subscribe: (channel: string, listener: WebSocketListener) => () => void;
};

export const WebSocketContext = createContext<WebSocketContextValue | null>(null);

function buildWebSocketUrl(pathname: string): string {
  if (typeof window === "undefined") return "";

  const { baseUrl } = apiClient.getConfig();
  // Always use window.location.origin for WebSocket base, since WS needs a full URL.
  // The API baseUrl may be a relative path like "/api" which is not valid for new URL().
  const url = new URL(window.location.origin);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  // If baseUrl is a full URL (SSR), extract the host; otherwise use current origin
  url.pathname = pathname;
  url.search = "";
  return url.toString();
}

// Exponential backoff configuration
const INITIAL_RETRY_DELAY = 1000;
const MAX_RETRY_DELAY = 30000;
const BACKOFF_MULTIPLIER = 2;

type Props = {
  children: ReactNode;
  enabled?: boolean;
  pathname?: string;
  reconnect?: boolean;
  url?: string;
};

export function WebSocketProvider({
  children,
  enabled = true,
  pathname = "/api/v1/ws/events",
  reconnect = true,
  url: customUrl,
}: Props) {
  const [status, setStatus] = useState<WebSocketStatus>("disconnected");
  const [connectionState, setConnectionState] = useState<ConnectionState>("disconnected");
  const [lastMessage, setLastMessage] = useState<WebSocketServerMessage | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<number | null>(null);
  const listenersRef = useRef<Map<string, Set<WebSocketListener>>>(new Map());
  const pendingSubscriptionsRef = useRef<Set<string>>(new Set());

  const clearReconnectTimer = () => {
    if (reconnectTimerRef.current) {
      window.clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  };

  const disconnect = useCallback(() => {
    clearReconnectTimer();
    reconnectAttemptRef.current = 0;

    const socket = socketRef.current;
    socketRef.current = null;

    if (
      socket &&
      (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)
    ) {
      try {
        socket.close();
      } catch {
        // ignore
      }
    }
    setStatus("disconnected");
    setConnectionState("disconnected");
  }, []);

  const dispatch = useCallback((message: WebSocketServerMessage) => {
    setLastMessage(message);

    const channel = message.channel;
    if (!channel) return;

    const listeners = listenersRef.current.get(channel);
    if (!listeners || listeners.size === 0) return;

    for (const listener of listeners) listener(message);
  }, []);

  const sendJson = useCallback((message: WebSocketClientMessage) => {
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    socket.send(JSON.stringify(message));
  }, []);

  // Alias for sendJson to match design interface
  const send = sendJson;

  const flushSubscriptions = useCallback(() => {
    const channels = Array.from(pendingSubscriptionsRef.current);
    if (channels.length === 0) return;
    pendingSubscriptionsRef.current.clear();
    sendJson({ type: "subscribe", channels });
  }, [sendJson]);

  const connect = useCallback(() => {
    if (!enabled || typeof window === "undefined") return;

    const existing = socketRef.current;
    if (
      existing &&
      (existing.readyState === WebSocket.OPEN || existing.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    clearReconnectTimer();
    setStatus("connecting");
    setConnectionState(reconnectAttemptRef.current > 0 ? "reconnecting" : "connecting");

    const url = customUrl || buildWebSocketUrl(pathname);
    if (!url) {
      setStatus("error");
      setConnectionState("disconnected");
      return;
    }

    const socket = new WebSocket(url);
    socketRef.current = socket;

    socket.onopen = () => {
      reconnectAttemptRef.current = 0;
      setStatus("connected");
      setConnectionState("connected");
      flushSubscriptions();
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as WebSocketServerMessage;
        dispatch(data);
      } catch {
        // ignore non-JSON payloads
      }
    };

    socket.onerror = () => {
      setStatus("error");
    };

    socket.onclose = () => {
      socketRef.current = null;
      setStatus("disconnected");
      setConnectionState("disconnected");

      if (!enabled || !reconnect) return;

      // Exponential backoff with configurable parameters
      const attempt = reconnectAttemptRef.current + 1;
      reconnectAttemptRef.current = attempt;
      const backoffMs = Math.min(
        MAX_RETRY_DELAY,
        INITIAL_RETRY_DELAY * Math.pow(BACKOFF_MULTIPLIER, Math.min(attempt - 1, 6))
      );

      setConnectionState("reconnecting");
      reconnectTimerRef.current = window.setTimeout(connect, backoffMs);
    };
  }, [customUrl, dispatch, enabled, flushSubscriptions, pathname, reconnect]);

  const subscribe = useCallback(
    (channel: string, listener: WebSocketListener) => {
      const listeners = listenersRef.current;
      const set = listeners.get(channel) ?? new Set<WebSocketListener>();
      set.add(listener);
      listeners.set(channel, set);

      const socket = socketRef.current;
      if (socket && socket.readyState === WebSocket.OPEN) {
        sendJson({ type: "subscribe", channels: [channel] });
      } else {
        pendingSubscriptionsRef.current.add(channel);
      }

      return () => {
        const current = listeners.get(channel);
        if (!current) return;
        current.delete(listener);
        if (current.size === 0) {
          listeners.delete(channel);
          const s = socketRef.current;
          if (s && s.readyState === WebSocket.OPEN) {
            sendJson({ type: "unsubscribe", channels: [channel] });
          }
        }
      };
    },
    [sendJson]
  );

  const isConnected = status === "connected";

  const value = useMemo<WebSocketContextValue>(
    () => ({
      status,
      connectionState,
      lastMessage,
      isConnected,
      connect,
      disconnect,
      sendJson,
      send,
      subscribe,
    }),
    [
      connect,
      connectionState,
      disconnect,
      isConnected,
      lastMessage,
      send,
      sendJson,
      status,
      subscribe,
    ]
  );

  useEffect(() => {
    if (!enabled) return;
    connect();
    return () => disconnect();
  }, [connect, disconnect, enabled]);

  return <WebSocketContext.Provider value={value}>{children}</WebSocketContext.Provider>;
}
