// Common TypeScript types for the application

export interface User {
  id: string
  email: string
  name: string | null
  createdAt: string
}

// Enums matching backend
export type SourceType = 'brave_search' | 'reddit' | 'rss'
export type DeliveryType = 'slack' | 'email' | 'sms'
export type RunStatus = 'pending' | 'running' | 'completed' | 'failed'

// Source Configuration
export interface SourceConfig {
  id: string
  winternId: string
  sourceType: SourceType
  config: Record<string, unknown>
  isActive: boolean
  createdAt: string
  updatedAt: string
}

export interface SourceConfigCreate {
  sourceType: SourceType
  config?: Record<string, unknown>
  isActive?: boolean
}

// Delivery Configuration
export interface DeliveryConfig {
  id: string
  winternId: string
  deliveryType: DeliveryType
  config: Record<string, unknown>
  isActive: boolean
  createdAt: string
  updatedAt: string
}

export interface DeliveryConfigCreate {
  deliveryType: DeliveryType
  config?: Record<string, unknown>
  isActive?: boolean
}

// Wintern
export interface Wintern {
  id: string
  userId: string
  name: string
  description: string | null
  context: string
  cronSchedule: string | null
  isActive: boolean
  nextRunAt: string | null
  createdAt: string
  updatedAt: string
  sourceConfigs: SourceConfig[]
  deliveryConfigs: DeliveryConfig[]
}

export interface WinternCreate {
  name: string
  description?: string | null
  context: string
  cronSchedule?: string | null
  sourceConfigs?: SourceConfigCreate[]
  deliveryConfigs?: DeliveryConfigCreate[]
}

export interface WinternUpdate {
  name?: string
  description?: string | null
  context?: string
  cronSchedule?: string | null
  isActive?: boolean
}

export interface WinternListResponse {
  items: Wintern[]
  total: number
  skip: number
  limit: number
}

// Wintern Runs
export interface WinternRun {
  id: string
  winternId: string
  status: RunStatus
  startedAt: string | null
  completedAt: string | null
  errorMessage: string | null
  digestContent: string | null
  metadata: Record<string, unknown> | null
  createdAt: string
  updatedAt: string
}

export interface WinternRunListResponse {
  items: WinternRun[]
  total: number
  skip: number
  limit: number
}

export interface TriggerRunResponse {
  winternId: string
  message: string
}

// API Error
export interface ApiError {
  message: string
  code: string
  details?: Record<string, unknown>
}

// Pagination params
export interface PaginationParams {
  skip?: number
  limit?: number
}
