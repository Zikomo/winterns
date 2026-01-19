import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

/**
 * Utility for merging Tailwind class names
 * Combines clsx for conditional classes with tailwind-merge for deduplication
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}

/**
 * Format a date for display
 * Returns fallback string for invalid dates
 */
export function formatDate(date: Date | string): string {
  const parsed = new Date(date)
  if (Number.isNaN(parsed.getTime())) {
    return 'Invalid date'
  }
  return new Intl.DateTimeFormat('en-US', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(parsed)
}

/**
 * Parse a cron schedule to a human-readable frequency string
 */
export function parseFrequency(cronSchedule: string | null): string {
  if (!cronSchedule) return 'Manual'

  const parts = cronSchedule.split(' ')
  if (parts.length !== 5) return 'Custom'

  const [minute, hour, dayOfMonth, month, dayOfWeek] = parts as [string, string, string, string, string]

  // Check for step values, ranges, or lists which indicate custom schedules
  const hasStepOrRange = (value: string) =>
    value.includes('/') || value.includes('-') || value.includes(',')

  // Check all fields for complex patterns
  if (
    hasStepOrRange(minute) ||
    hasStepOrRange(hour) ||
    hasStepOrRange(dayOfMonth) ||
    hasStepOrRange(month) ||
    hasStepOrRange(dayOfWeek)
  ) {
    return 'Custom'
  }

  // Hourly: runs every hour at a specific minute
  if (minute !== '*' && hour === '*' && dayOfMonth === '*' && month === '*' && dayOfWeek === '*') {
    return 'Hourly'
  }

  // Daily: runs every day at a specific time (both minute and hour are specific)
  if (minute !== '*' && hour !== '*' && dayOfMonth === '*' && month === '*' && dayOfWeek === '*') {
    return 'Daily'
  }

  // Weekly: runs on specific day(s) of the week
  if (dayOfMonth === '*' && month === '*' && dayOfWeek !== '*') {
    return 'Weekly'
  }

  // Monthly: runs on specific day of month
  if (dayOfMonth !== '*' && month === '*' && dayOfWeek === '*') {
    return 'Monthly'
  }

  return 'Custom'
}

/**
 * Format a relative time string from a date
 * Uses Math.floor for past (conservative) and Math.ceil for future (rounds up)
 * to avoid "0m ago" or "in 0m" edge cases
 */
export function formatRelativeTime(dateString: string | null): string {
  if (!dateString) return 'Not scheduled'

  const date = new Date(dateString)
  if (Number.isNaN(date.getTime())) {
    return 'Invalid date'
  }

  const now = new Date()
  const diffMs = date.getTime() - now.getTime()
  const absDiffMs = Math.abs(diffMs)

  // Use floor for past, ceil for future to avoid "0" and boundary issues
  const minutesAgo = Math.floor(absDiffMs / (1000 * 60))
  const hoursAgo = Math.floor(absDiffMs / (1000 * 60 * 60))
  const daysAgo = Math.floor(absDiffMs / (1000 * 60 * 60 * 24))

  const minutesFuture = Math.ceil(absDiffMs / (1000 * 60))
  const hoursFuture = Math.ceil(absDiffMs / (1000 * 60 * 60))
  const daysFuture = Math.ceil(absDiffMs / (1000 * 60 * 60 * 24))

  if (diffMs < 0) {
    // Past - use floor (conservative: "2m ago" not "3m ago" for 2.5 mins)
    if (minutesAgo === 0) return 'just now'
    if (minutesAgo < 60) return `${minutesAgo}m ago`
    if (hoursAgo < 24) return `${hoursAgo}h ago`
    if (daysAgo < 7) return `${daysAgo}d ago`
    return formatDate(date)
  }

  // Future - use ceil (conservative: "in 3m" not "in 2m" for 2.5 mins)
  if (minutesFuture === 0) return 'now'
  if (minutesFuture < 60) return `in ${minutesFuture}m`
  if (hoursFuture < 24) return `in ${hoursFuture}h`
  if (daysFuture < 7) return `in ${daysFuture}d`
  return formatDate(date)
}
