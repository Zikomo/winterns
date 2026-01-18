import axios from 'axios'

// Case transformation utilities
function camelToSnake(str: string): string {
  return str.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`)
}

function snakeToCamel(str: string): string {
  return str.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())
}

function isPlainObject(obj: unknown): obj is Record<string, unknown> {
  return Object.prototype.toString.call(obj) === '[object Object]'
}

function transformKeys<T>(obj: unknown, transformer: (key: string) => string): T {
  if (obj === null || obj === undefined) {
    return obj as T
  }

  if (Array.isArray(obj)) {
    return obj.map((item) => transformKeys(item, transformer)) as T
  }

  // Only transform plain objects - skip FormData, Blob, Date, URLSearchParams, etc.
  if (isPlainObject(obj)) {
    const transformed: Record<string, unknown> = {}
    for (const [key, value] of Object.entries(obj)) {
      transformed[transformer(key)] = transformKeys(value, transformer)
    }
    return transformed as T
  }

  return obj as T
}

export function toSnakeCase<T>(obj: unknown): T {
  return transformKeys<T>(obj, camelToSnake)
}

export function toCamelCase<T>(obj: unknown): T {
  return transformKeys<T>(obj, snakeToCamel)
}

export const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor for adding auth token and converting to snake_case
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }

  // Convert request body from camelCase to snake_case
  if (config.data && typeof config.data === 'object') {
    config.data = toSnakeCase(config.data)
  }

  return config
})

// Response interceptor for handling errors and converting to camelCase
api.interceptors.response.use(
  (response) => {
    // Convert response data from snake_case to camelCase
    if (response.data && typeof response.data === 'object') {
      response.data = toCamelCase(response.data)
    }
    return response
  },
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// Health check API
export async function checkHealth(): Promise<{ status: string }> {
  const response = await api.get<{ status: string }>('/health')
  return response.data
}
