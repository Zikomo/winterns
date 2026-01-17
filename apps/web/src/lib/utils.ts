import { type ClassValue, clsx } from 'clsx'

/**
 * Utility for merging class names
 * Note: Install clsx if using this: pnpm add clsx
 */
export function cn(...inputs: ClassValue[]): string {
  return clsx(inputs)
}

/**
 * Format a date for display
 */
export function formatDate(date: Date | string): string {
  return new Intl.DateTimeFormat('en-US', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(date))
}
