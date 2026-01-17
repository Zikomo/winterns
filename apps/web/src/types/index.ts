// Common TypeScript types for the application

export interface User {
  id: string
  email: string
  name: string | null
  createdAt: string
}

export interface Wintern {
  id: string
  name: string
  context: string
  objectives: string[]
  schedule: string
  isActive: boolean
  userId: string
  createdAt: string
  updatedAt: string
}

export interface WinternRun {
  id: string
  winternId: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  startedAt: string
  completedAt: string | null
  itemCount: number | null
  error: string | null
}

export interface ApiError {
  message: string
  code: string
  details?: Record<string, unknown>
}
