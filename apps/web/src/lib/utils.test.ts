import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { parseFrequency, formatRelativeTime, formatDate } from './utils'

describe('parseFrequency', () => {
  it('returns "Manual" for null schedule', () => {
    expect(parseFrequency(null)).toBe('Manual')
  })

  it('returns "Custom" for invalid cron format', () => {
    expect(parseFrequency('invalid')).toBe('Custom')
    expect(parseFrequency('* * *')).toBe('Custom')
    expect(parseFrequency('* * * * * *')).toBe('Custom')
  })

  it('returns "Daily" for daily schedules', () => {
    expect(parseFrequency('0 9 * * *')).toBe('Daily')
    expect(parseFrequency('30 14 * * *')).toBe('Daily')
    expect(parseFrequency('0 0 * * *')).toBe('Daily')
  })

  it('returns "Weekly" for weekly schedules', () => {
    expect(parseFrequency('0 9 * * 1')).toBe('Weekly')
    expect(parseFrequency('30 10 * * MON')).toBe('Weekly')
    expect(parseFrequency('0 9 * * 0')).toBe('Weekly')
  })

  it('returns "Monthly" for monthly schedules', () => {
    expect(parseFrequency('0 9 1 * *')).toBe('Monthly')
    expect(parseFrequency('0 9 15 * *')).toBe('Monthly')
    expect(parseFrequency('30 10 28 * *')).toBe('Monthly')
  })

  it('returns "Hourly" for hourly schedules', () => {
    expect(parseFrequency('0 * * * *')).toBe('Hourly')
    expect(parseFrequency('30 * * * *')).toBe('Hourly')
    expect(parseFrequency('15 * * * *')).toBe('Hourly')
  })

  it('returns "Custom" for complex schedules', () => {
    expect(parseFrequency('0 9 1 1 *')).toBe('Custom') // Yearly
    expect(parseFrequency('*/5 * * * *')).toBe('Custom') // Every 5 minutes
    expect(parseFrequency('0 9 1 * 1')).toBe('Custom') // Mixed day of month and week
  })

  it('returns "Custom" for multi-value day/month/week fields', () => {
    expect(parseFrequency('0 9 1,15 * *')).toBe('Custom') // Multiple days of month
    expect(parseFrequency('0 9 * * 1-5')).toBe('Custom') // Weekday range
    expect(parseFrequency('0 9 * * 0,6')).toBe('Custom') // Weekend days
    expect(parseFrequency('0 9 * 1,6 *')).toBe('Custom') // Multiple months
    expect(parseFrequency('0 9 1-7 * *')).toBe('Custom') // Day range
  })
})

describe('formatRelativeTime', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2024-01-15T12:00:00Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns "Not scheduled" for null', () => {
    expect(formatRelativeTime(null)).toBe('Not scheduled')
  })

  it('returns "Not scheduled" for empty string', () => {
    expect(formatRelativeTime('')).toBe('Not scheduled')
  })

  it('returns "Invalid date" for malformed date strings', () => {
    expect(formatRelativeTime('not-a-date')).toBe('Invalid date')
    expect(formatRelativeTime('2024-13-45')).toBe('Invalid date')
    expect(formatRelativeTime('abc123')).toBe('Invalid date')
  })

  describe('future dates', () => {
    it('returns "now" for times less than a minute away', () => {
      expect(formatRelativeTime('2024-01-15T12:00:00Z')).toBe('now')
      expect(formatRelativeTime('2024-01-15T12:00:30Z')).toBe('in 1m')
    })

    it('formats minutes in the future', () => {
      expect(formatRelativeTime('2024-01-15T12:30:00Z')).toBe('in 30m')
      expect(formatRelativeTime('2024-01-15T12:45:00Z')).toBe('in 45m')
    })

    it('formats hours in the future', () => {
      expect(formatRelativeTime('2024-01-15T14:00:00Z')).toBe('in 2h')
      expect(formatRelativeTime('2024-01-15T20:00:00Z')).toBe('in 8h')
    })

    it('formats days in the future', () => {
      expect(formatRelativeTime('2024-01-17T12:00:00Z')).toBe('in 2d')
      expect(formatRelativeTime('2024-01-20T12:00:00Z')).toBe('in 5d')
    })

    it('formats dates beyond a week', () => {
      const result = formatRelativeTime('2024-01-25T12:00:00Z')
      expect(result).toContain('Jan')
      expect(result).toContain('25')
    })
  })

  describe('past dates', () => {
    it('returns "just now" for times less than a minute ago', () => {
      expect(formatRelativeTime('2024-01-15T11:59:30Z')).toBe('just now')
      expect(formatRelativeTime('2024-01-15T11:59:01Z')).toBe('just now')
    })

    it('formats minutes in the past', () => {
      expect(formatRelativeTime('2024-01-15T11:30:00Z')).toBe('30m ago')
      expect(formatRelativeTime('2024-01-15T11:15:00Z')).toBe('45m ago')
    })

    it('formats hours in the past', () => {
      expect(formatRelativeTime('2024-01-15T10:00:00Z')).toBe('2h ago')
      expect(formatRelativeTime('2024-01-15T04:00:00Z')).toBe('8h ago')
    })

    it('formats days in the past', () => {
      expect(formatRelativeTime('2024-01-13T12:00:00Z')).toBe('2d ago')
      expect(formatRelativeTime('2024-01-10T12:00:00Z')).toBe('5d ago')
    })

    it('formats dates beyond a week ago', () => {
      const result = formatRelativeTime('2024-01-05T12:00:00Z')
      expect(result).toContain('Jan')
      expect(result).toContain('5')
    })
  })
})

describe('formatDate', () => {
  it('formats date string correctly', () => {
    const result = formatDate('2024-01-15T09:30:00Z')
    expect(result).toContain('Jan')
    expect(result).toContain('15')
    expect(result).toContain('2024')
  })

  it('formats Date object correctly', () => {
    const result = formatDate(new Date('2024-06-20T14:45:00Z'))
    expect(result).toContain('Jun')
    expect(result).toContain('20')
    expect(result).toContain('2024')
  })

  it('returns "Invalid date" for malformed inputs', () => {
    expect(formatDate('not-a-date')).toBe('Invalid date')
    expect(formatDate('')).toBe('Invalid date')
    expect(formatDate(new Date('invalid'))).toBe('Invalid date')
  })
})
