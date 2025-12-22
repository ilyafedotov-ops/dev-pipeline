/**
 * Property-Based Tests for Burndown Chart Component
 * **Feature: frontend-comprehensive-refactor**
 * 
 * Property 8: Burndown dual line rendering
 * 
 * **Validates: Requirements 5.2**
 */

import { describe, it, expect } from 'vitest'
import * as fc from 'fast-check'
import { countBurndownLines, formatDateLabel } from '@/components/visualizations/burndown-chart'
import type { BurndownPoint } from '@/lib/api/types'

// Arbitrary generator for valid date strings
const validDateArbitrary = fc.integer({
  min: new Date('2020-01-01').getTime(),
  max: new Date('2030-12-31').getTime()
}).map(ts => new Date(ts).toISOString().split('T')[0])

// Arbitrary generator for non-negative numbers (points remaining)
const pointsArbitrary = fc.nat({ max: 1000 })

// Arbitrary generator for a single BurndownPoint
const burndownPointArbitrary: fc.Arbitrary<BurndownPoint> = fc.record({
  date: validDateArbitrary,
  ideal: pointsArbitrary,
  actual: pointsArbitrary
})

// Arbitrary generator for a list of BurndownPoints (at least 1 point)
const burndownDataArbitrary = fc.array(burndownPointArbitrary, { minLength: 1, maxLength: 30 })

// Arbitrary generator for empty or valid burndown data
const burndownDataWithEmptyArbitrary = fc.oneof(
  fc.constant([] as BurndownPoint[]),
  burndownDataArbitrary
)

describe('Burndown Chart Property Tests', () => {
  /**
   * Property 8: Burndown dual line rendering
   * For any burndown data with at least one point, the chart SHALL render
   * exactly two lines: one for ideal and one for actual burndown.
   * **Validates: Requirements 5.2**
   */
  describe('Property 8: Burndown dual line rendering', () => {
    it('should have both ideal and actual lines for non-empty data', () => {
      fc.assert(
        fc.property(burndownDataArbitrary, (data) => {
          const lines = countBurndownLines(data)
          
          // For non-empty data, both lines should be present
          expect(lines.idealLine).toBe(true)
          expect(lines.actualLine).toBe(true)
        }),
        { numRuns: 100 }
      )
    })

    it('should have no lines for empty data', () => {
      const lines = countBurndownLines([])
      
      expect(lines.idealLine).toBe(false)
      expect(lines.actualLine).toBe(false)
    })

    it('should always have exactly two line types when data is present', () => {
      fc.assert(
        fc.property(burndownDataArbitrary, (data) => {
          const lines = countBurndownLines(data)
          
          // Count the number of line types
          const lineCount = (lines.idealLine ? 1 : 0) + (lines.actualLine ? 1 : 0)
          
          // Should always be exactly 2 lines for valid data
          expect(lineCount).toBe(2)
        }),
        { numRuns: 100 }
      )
    })

    it('should preserve line presence regardless of data values', () => {
      fc.assert(
        fc.property(
          fc.array(
            fc.record({
              date: validDateArbitrary,
              ideal: fc.integer({ min: 0, max: 10000 }),
              actual: fc.integer({ min: 0, max: 10000 })
            }),
            { minLength: 1, maxLength: 50 }
          ),
          (data) => {
            const lines = countBurndownLines(data)
            
            // Lines should be present regardless of the actual numeric values
            expect(lines.idealLine).toBe(true)
            expect(lines.actualLine).toBe(true)
          }
        ),
        { numRuns: 100 }
      )
    })

    it('should handle single data point', () => {
      fc.assert(
        fc.property(burndownPointArbitrary, (point) => {
          const lines = countBurndownLines([point])
          
          // Even with a single point, both lines should be present
          expect(lines.idealLine).toBe(true)
          expect(lines.actualLine).toBe(true)
        }),
        { numRuns: 100 }
      )
    })
  })

  /**
   * Additional property tests for date formatting
   */
  describe('Date formatting', () => {
    it('should format valid dates consistently', () => {
      fc.assert(
        fc.property(validDateArbitrary, (dateStr) => {
          const formatted = formatDateLabel(dateStr)
          
          // Should return a non-empty string
          expect(formatted.length).toBeGreaterThan(0)
          
          // Should not return the original ISO date string
          // (it should be formatted to "Mon DD" format)
          expect(formatted).not.toBe(dateStr)
        }),
        { numRuns: 100 }
      )
    })

    it('should return original value for invalid dates', () => {
      fc.assert(
        fc.property(
          fc.string({ minLength: 1, maxLength: 20 }).filter(s => {
            const date = new Date(s)
            return Number.isNaN(date.getTime())
          }),
          (invalidDate) => {
            const formatted = formatDateLabel(invalidDate)
            
            // Should return the original string for invalid dates
            expect(formatted).toBe(invalidDate)
          }
        ),
        { numRuns: 100 }
      )
    })
  })
})
