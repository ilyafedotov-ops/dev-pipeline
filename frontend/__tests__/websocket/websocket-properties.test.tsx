/**
 * Property-Based Tests for WebSocket Infrastructure
 * **Feature: frontend-comprehensive-refactor, Property 1: WebSocket message delivery to subscribers**
 * **Validates: Requirements 2.3**
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import * as fc from 'fast-check'
import { renderHook, act, waitFor } from '@testing-library/react'
import { WebSocketProvider } from '@/lib/websocket/context'
import { useWebSocket, useSubscription } from '@/lib/websocket/hooks'
import type { WebSocketServerMessage } from '@/lib/websocket/types'
import type { ReactNode } from 'react'

// Mock WebSocket implementation for testing
class MockWebSocket {
  static instances: MockWebSocket[] = []
  
  url: string
  readyState: number = WebSocket.CONNECTING
  onopen: ((event: Event) => void) | null = null
  onclose: ((event: CloseEvent) => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  
  private sentMessages: string[] = []
  
  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this)
  }
  
  // Call this to simulate the connection opening
  simulateOpen() {
    this.readyState = WebSocket.OPEN
    if (this.onopen) {
      this.onopen(new Event('open'))
    }
  }
  
  send(data: string) {
    this.sentMessages.push(data)
  }
  
  close() {
    this.readyState = WebSocket.CLOSED
    if (this.onclose) {
      this.onclose(new CloseEvent('close'))
    }
  }
  
  // Test helper to simulate receiving a message
  simulateMessage(data: WebSocketServerMessage) {
    if (this.onmessage) {
      this.onmessage(new MessageEvent('message', { data: JSON.stringify(data) }))
    }
  }
  
  getSentMessages(): string[] {
    return this.sentMessages
  }
  
  static reset() {
    MockWebSocket.instances = []
  }
  
  static getLastInstance(): MockWebSocket | undefined {
    return MockWebSocket.instances[MockWebSocket.instances.length - 1]
  }
}

// Setup global WebSocket mock
const originalWebSocket = global.WebSocket
beforeEach(() => {
  MockWebSocket.reset()
  // @ts-expect-error - Mocking WebSocket
  global.WebSocket = MockWebSocket
})

afterEach(() => {
  global.WebSocket = originalWebSocket
})

// Wrapper component for testing hooks
function createWrapper(url: string = 'ws://localhost:8000/ws/events') {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <WebSocketProvider url={url} enabled={true}>
        {children}
      </WebSocketProvider>
    )
  }
}

// Arbitrary generators for property-based testing
const channelArbitrary = fc.oneof(
  fc.nat({ max: 1000 }).map(n => `protocol:${n}`),
  fc.nat({ max: 1000 }).map(n => `step:${n}`),
  fc.constant('events'),
  fc.constant('agents')
)

const messageTypeArbitrary = fc.oneof(
  fc.constant('protocol_update' as const),
  fc.constant('step_update' as const),
  fc.constant('event' as const),
  fc.constant('ping' as const),
  fc.constant('pong' as const)
)

// Use integer timestamps to avoid invalid date issues
// Generate timestamps between 2020-01-01 and 2030-12-31
const minTimestamp = new Date('2020-01-01').getTime()
const maxTimestamp = new Date('2030-12-31').getTime()
const validDateArbitrary = fc.integer({ min: minTimestamp, max: maxTimestamp })
  .map(ts => new Date(ts).toISOString())

const payloadArbitrary = fc.oneof(
  fc.record({
    id: fc.nat({ max: 1000 }),
    status: fc.oneof(fc.constant('running'), fc.constant('completed'), fc.constant('failed'), fc.constant('pending')),
    updated_at: validDateArbitrary
  }),
  fc.record({
    id: fc.nat({ max: 1000 }),
    status: fc.string(),
    started_at: fc.option(validDateArbitrary),
    finished_at: fc.option(validDateArbitrary)
  }),
  fc.record({
    id: fc.nat({ max: 1000 }),
    name: fc.string({ minLength: 1, maxLength: 50 })
  })
)

describe('WebSocket Property Tests', () => {
  /**
   * Property 1: WebSocket message delivery to subscribers
   * For any channel subscription and any message received on that channel,
   * the subscribed callback SHALL be invoked with the message payload.
   * **Validates: Requirements 2.3**
   */
  it('Property 1: messages on subscribed channels are delivered to subscribers', async () => {
    await fc.assert(
      fc.asyncProperty(
        channelArbitrary,
        messageTypeArbitrary,
        payloadArbitrary,
        async (channel, messageType, payload) => {
          // Create a message for the specific subscribed channel
          // Using WebSocketEnvelope structure (ts field instead of timestamp)
          const message: WebSocketServerMessage = {
            type: messageType,
            channel: channel,
            payload: payload,
            ts: new Date().toISOString(),
          }
          
          const receivedMessages: WebSocketServerMessage[] = []
          const callback = vi.fn((msg: WebSocketServerMessage) => {
            receivedMessages.push(msg)
          })
          
          // Render the hook with subscription
          const { result, unmount } = renderHook(
            () => {
              const ws = useWebSocket()
              useSubscription(channel, callback)
              return ws
            },
            { wrapper: createWrapper() }
          )
          
          // Get the mock WebSocket instance
          const mockWs = MockWebSocket.getLastInstance()
          expect(mockWs).toBeDefined()
          
          // Simulate the connection opening
          act(() => {
            mockWs!.simulateOpen()
          })
          
          // Wait for connection to be established
          await waitFor(() => {
            expect(result.current.status).toBe('connected')
          }, { timeout: 1000 })
          
          // Simulate receiving a message on the subscribed channel
          act(() => {
            mockWs!.simulateMessage(message)
          })
          
          // Verify the callback was invoked with the message
          expect(callback).toHaveBeenCalledTimes(1)
          expect(callback).toHaveBeenCalledWith(expect.objectContaining({
            channel: channel,
            type: messageType,
          }))
          
          // Verify the received message matches what was sent
          expect(receivedMessages).toHaveLength(1)
          expect(receivedMessages[0].channel).toBe(channel)
          
          unmount()
        }
      ),
      { numRuns: 100 }
    )
  }, 60000) // 60 second timeout for property test
})
