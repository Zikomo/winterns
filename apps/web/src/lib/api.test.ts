import { describe, it, expect } from 'vitest'
import { toSnakeCase, toCamelCase } from './api'

describe('case transformers - non-plain objects', () => {
  it('does not transform Date objects', () => {
    const date = new Date('2024-01-01')
    expect(toSnakeCase(date)).toBe(date)
    expect(toCamelCase(date)).toBe(date)
  })

  it('does not transform URLSearchParams', () => {
    const params = new URLSearchParams()
    params.append('user_name', 'test')
    expect(toSnakeCase(params)).toBe(params)
    expect(toCamelCase(params)).toBe(params)
  })

  it('does not transform FormData', () => {
    const formData = new FormData()
    expect(toSnakeCase(formData)).toBe(formData)
    expect(toCamelCase(formData)).toBe(formData)
  })

  it('does not transform Blob', () => {
    const blob = new Blob(['test'], { type: 'text/plain' })
    expect(toSnakeCase(blob)).toBe(blob)
    expect(toCamelCase(blob)).toBe(blob)
  })

  it('does not transform ArrayBuffer', () => {
    const buffer = new ArrayBuffer(8)
    expect(toSnakeCase(buffer)).toBe(buffer)
    expect(toCamelCase(buffer)).toBe(buffer)
  })

  it('preserves Date objects inside plain objects', () => {
    const date = new Date('2024-01-01')
    const input = { createdAt: date, userName: 'test' }
    const result = toSnakeCase<{ created_at: Date; user_name: string }>(input)
    expect(result.created_at).toBe(date)
    expect(result.user_name).toBe('test')
  })
})

describe('toSnakeCase', () => {
  it('converts simple camelCase to snake_case', () => {
    expect(toSnakeCase({ cronSchedule: '0 9 * * *' })).toEqual({ cron_schedule: '0 9 * * *' })
  })

  it('converts nested objects', () => {
    const input = {
      winternId: '123',
      sourceConfigs: [
        { sourceType: 'brave_search', isActive: true },
      ],
    }
    const expected = {
      wintern_id: '123',
      source_configs: [
        { source_type: 'brave_search', is_active: true },
      ],
    }
    expect(toSnakeCase(input)).toEqual(expected)
  })

  it('handles null and undefined', () => {
    expect(toSnakeCase(null)).toBe(null)
    expect(toSnakeCase(undefined)).toBe(undefined)
  })

  it('handles primitive values', () => {
    expect(toSnakeCase('test')).toBe('test')
    expect(toSnakeCase(123)).toBe(123)
    expect(toSnakeCase(true)).toBe(true)
  })

  it('handles arrays of primitives', () => {
    expect(toSnakeCase(['a', 'b', 'c'])).toEqual(['a', 'b', 'c'])
  })

  it('handles deeply nested objects', () => {
    const input = {
      topLevel: {
        midLevel: {
          deepLevel: {
            someValue: 'test',
          },
        },
      },
    }
    const expected = {
      top_level: {
        mid_level: {
          deep_level: {
            some_value: 'test',
          },
        },
      },
    }
    expect(toSnakeCase(input)).toEqual(expected)
  })
})

describe('toCamelCase', () => {
  it('converts simple snake_case to camelCase', () => {
    expect(toCamelCase({ cron_schedule: '0 9 * * *' })).toEqual({ cronSchedule: '0 9 * * *' })
  })

  it('converts nested objects', () => {
    const input = {
      wintern_id: '123',
      source_configs: [
        { source_type: 'brave_search', is_active: true },
      ],
    }
    const expected = {
      winternId: '123',
      sourceConfigs: [
        { sourceType: 'brave_search', isActive: true },
      ],
    }
    expect(toCamelCase(input)).toEqual(expected)
  })

  it('handles null and undefined', () => {
    expect(toCamelCase(null)).toBe(null)
    expect(toCamelCase(undefined)).toBe(undefined)
  })

  it('handles typical API response', () => {
    const apiResponse = {
      id: 'abc-123',
      user_id: 'user-456',
      name: 'Test Wintern',
      cron_schedule: '0 9 * * *',
      is_active: true,
      next_run_at: '2024-01-15T09:00:00Z',
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
      source_configs: [],
      delivery_configs: [],
    }
    const expected = {
      id: 'abc-123',
      userId: 'user-456',
      name: 'Test Wintern',
      cronSchedule: '0 9 * * *',
      isActive: true,
      nextRunAt: '2024-01-15T09:00:00Z',
      createdAt: '2024-01-01T00:00:00Z',
      updatedAt: '2024-01-01T00:00:00Z',
      sourceConfigs: [],
      deliveryConfigs: [],
    }
    expect(toCamelCase(apiResponse)).toEqual(expected)
  })
})
