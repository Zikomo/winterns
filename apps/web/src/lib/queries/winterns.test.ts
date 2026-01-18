import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement, type ReactNode } from 'react'
import {
  useWinterns,
  useWintern,
  useCreateWintern,
  useUpdateWintern,
  useDeleteWintern,
  useTriggerRun,
  useWinternRuns,
  useWinternRun,
  winternKeys,
} from './winterns'
import type { Wintern, WinternListResponse, WinternRun, WinternRunListResponse } from '@/types'

// Mock the api module
vi.mock('@/lib/api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

import { api } from '@/lib/api'

const mockApi = api as {
  get: ReturnType<typeof vi.fn>
  post: ReturnType<typeof vi.fn>
  put: ReturnType<typeof vi.fn>
  delete: ReturnType<typeof vi.fn>
}

// Test data factories
const createMockWintern = (overrides: Partial<Wintern> = {}): Wintern => ({
  id: 'wintern-1',
  userId: 'user-1',
  name: 'Test Wintern',
  description: 'A test wintern',
  context: 'Test context for AI research',
  cronSchedule: '0 9 * * *',
  isActive: true,
  nextRunAt: '2024-01-15T09:00:00Z',
  createdAt: '2024-01-01T00:00:00Z',
  updatedAt: '2024-01-01T00:00:00Z',
  sourceConfigs: [],
  deliveryConfigs: [],
  ...overrides,
})

const createMockRun = (overrides: Partial<WinternRun> = {}): WinternRun => ({
  id: 'run-1',
  winternId: 'wintern-1',
  status: 'completed',
  startedAt: '2024-01-01T09:00:00Z',
  completedAt: '2024-01-01T09:05:00Z',
  errorMessage: null,
  digestContent: 'Test digest content',
  metadata: { itemsFound: 10, itemsDelivered: 5 },
  createdAt: '2024-01-01T09:00:00Z',
  updatedAt: '2024-01-01T09:05:00Z',
  ...overrides,
})

// Test wrapper with QueryClient
function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  })

  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(QueryClientProvider, { client: queryClient }, children)
  }
}

describe('winternKeys', () => {
  it('generates correct query keys', () => {
    expect(winternKeys.all).toEqual(['winterns'])
    expect(winternKeys.lists()).toEqual(['winterns', 'list'])
    expect(winternKeys.list({ skip: 0, limit: 10 })).toEqual(['winterns', 'list', { skip: 0, limit: 10 }])
    expect(winternKeys.details()).toEqual(['winterns', 'detail'])
    expect(winternKeys.detail('123')).toEqual(['winterns', 'detail', '123'])
    expect(winternKeys.runs('123')).toEqual(['winterns', 'detail', '123', 'runs'])
  })
})

describe('useWinterns', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches winterns list successfully', async () => {
    const mockResponse: WinternListResponse = {
      items: [createMockWintern(), createMockWintern({ id: 'wintern-2', name: 'Second Wintern' })],
      total: 2,
      skip: 0,
      limit: 20,
    }
    mockApi.get.mockResolvedValueOnce({ data: mockResponse })

    const { result } = renderHook(() => useWinterns(), { wrapper: createWrapper() })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(mockApi.get).toHaveBeenCalledWith('/v1/winterns')
    expect(result.current.data).toEqual(mockResponse)
    expect(result.current.data?.items).toHaveLength(2)
  })

  it('passes pagination params', async () => {
    const mockResponse: WinternListResponse = { items: [], total: 0, skip: 10, limit: 5 }
    mockApi.get.mockResolvedValueOnce({ data: mockResponse })

    const { result } = renderHook(() => useWinterns({ skip: 10, limit: 5 }), { wrapper: createWrapper() })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(mockApi.get).toHaveBeenCalledWith('/v1/winterns?skip=10&limit=5')
  })

  it('handles error', async () => {
    mockApi.get.mockRejectedValueOnce(new Error('Network error'))

    const { result } = renderHook(() => useWinterns(), { wrapper: createWrapper() })

    await waitFor(() => expect(result.current.isError).toBe(true))

    expect(result.current.error).toBeInstanceOf(Error)
  })
})

describe('useWintern', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches single wintern successfully', async () => {
    const mockWintern = createMockWintern()
    mockApi.get.mockResolvedValueOnce({ data: mockWintern })

    const { result } = renderHook(() => useWintern('wintern-1'), { wrapper: createWrapper() })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(mockApi.get).toHaveBeenCalledWith('/v1/winterns/wintern-1')
    expect(result.current.data).toEqual(mockWintern)
  })

  it('does not fetch when id is undefined', () => {
    renderHook(() => useWintern(undefined), { wrapper: createWrapper() })

    expect(mockApi.get).not.toHaveBeenCalled()
  })
})

describe('useCreateWintern', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('creates wintern successfully', async () => {
    const newWintern = createMockWintern()
    mockApi.post.mockResolvedValueOnce({ data: newWintern })

    const { result } = renderHook(() => useCreateWintern(), { wrapper: createWrapper() })

    result.current.mutate({
      name: 'Test Wintern',
      context: 'Test context',
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(mockApi.post).toHaveBeenCalledWith('/v1/winterns', {
      name: 'Test Wintern',
      context: 'Test context',
    })
    expect(result.current.data).toEqual(newWintern)
  })
})

describe('useUpdateWintern', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('updates wintern successfully', async () => {
    const updatedWintern = createMockWintern({ name: 'Updated Name' })
    mockApi.put.mockResolvedValueOnce({ data: updatedWintern })

    const { result } = renderHook(() => useUpdateWintern(), { wrapper: createWrapper() })

    result.current.mutate({
      id: 'wintern-1',
      data: { name: 'Updated Name' },
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(mockApi.put).toHaveBeenCalledWith('/v1/winterns/wintern-1', { name: 'Updated Name' })
    expect(result.current.data).toEqual(updatedWintern)
  })
})

describe('useDeleteWintern', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('deletes wintern successfully', async () => {
    mockApi.delete.mockResolvedValueOnce({})

    const { result } = renderHook(() => useDeleteWintern(), { wrapper: createWrapper() })

    result.current.mutate('wintern-1')

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(mockApi.delete).toHaveBeenCalledWith('/v1/winterns/wintern-1')
    expect(result.current.data).toBe('wintern-1')
  })
})

describe('useTriggerRun', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('triggers run successfully', async () => {
    const mockResponse = {
      winternId: 'wintern-1',
      message: 'Execution has been queued.',
    }
    mockApi.post.mockResolvedValueOnce({ data: mockResponse })

    const { result } = renderHook(() => useTriggerRun(), { wrapper: createWrapper() })

    result.current.mutate('wintern-1')

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(mockApi.post).toHaveBeenCalledWith('/v1/winterns/wintern-1/run')
    expect(result.current.data).toEqual(mockResponse)
  })
})

describe('useWinternRuns', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches runs list successfully', async () => {
    const mockResponse: WinternRunListResponse = {
      items: [createMockRun(), createMockRun({ id: 'run-2', status: 'running' })],
      total: 2,
      skip: 0,
      limit: 20,
    }
    mockApi.get.mockResolvedValueOnce({ data: mockResponse })

    const { result } = renderHook(() => useWinternRuns('wintern-1'), { wrapper: createWrapper() })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(mockApi.get).toHaveBeenCalledWith('/v1/winterns/wintern-1/runs')
    expect(result.current.data?.items).toHaveLength(2)
  })

  it('does not fetch when winternId is undefined', () => {
    renderHook(() => useWinternRuns(undefined), { wrapper: createWrapper() })

    expect(mockApi.get).not.toHaveBeenCalled()
  })

  it('passes pagination params', async () => {
    const mockResponse: WinternRunListResponse = { items: [], total: 0, skip: 5, limit: 10 }
    mockApi.get.mockResolvedValueOnce({ data: mockResponse })

    const { result } = renderHook(
      () => useWinternRuns('wintern-1', { skip: 5, limit: 10 }),
      { wrapper: createWrapper() }
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(mockApi.get).toHaveBeenCalledWith('/v1/winterns/wintern-1/runs?skip=5&limit=10')
  })
})

describe('useWinternRun', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches single run successfully', async () => {
    const mockRun = createMockRun()
    mockApi.get.mockResolvedValueOnce({ data: mockRun })

    const { result } = renderHook(
      () => useWinternRun('wintern-1', 'run-1'),
      { wrapper: createWrapper() }
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(mockApi.get).toHaveBeenCalledWith('/v1/winterns/wintern-1/runs/run-1')
    expect(result.current.data).toEqual(mockRun)
  })

  it('does not fetch when winternId is undefined', () => {
    renderHook(() => useWinternRun(undefined, 'run-1'), { wrapper: createWrapper() })

    expect(mockApi.get).not.toHaveBeenCalled()
  })

  it('does not fetch when runId is undefined', () => {
    renderHook(() => useWinternRun('wintern-1', undefined), { wrapper: createWrapper() })

    expect(mockApi.get).not.toHaveBeenCalled()
  })
})
