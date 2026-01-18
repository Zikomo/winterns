import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type {
  Wintern,
  WinternCreate,
  WinternUpdate,
  WinternListResponse,
  WinternRun,
  WinternRunListResponse,
  TriggerRunResponse,
  PaginationParams,
} from '@/types'

// Query keys
export const winternKeys = {
  all: ['winterns'] as const,
  lists: () => [...winternKeys.all, 'list'] as const,
  list: (params: PaginationParams) => [...winternKeys.lists(), params] as const,
  details: () => [...winternKeys.all, 'detail'] as const,
  detail: (id: string) => [...winternKeys.details(), id] as const,
  runs: (winternId: string) => [...winternKeys.detail(winternId), 'runs'] as const,
  runList: (winternId: string, params: PaginationParams) =>
    [...winternKeys.runs(winternId), params] as const,
  run: (winternId: string, runId: string) =>
    [...winternKeys.runs(winternId), runId] as const,
}

// List Winterns
export function useWinterns(params: PaginationParams = {}) {
  return useQuery({
    queryKey: winternKeys.list(params),
    queryFn: async () => {
      const searchParams = new URLSearchParams()
      if (params.skip !== undefined) searchParams.set('skip', String(params.skip))
      if (params.limit !== undefined) searchParams.set('limit', String(params.limit))
      const query = searchParams.toString()
      const url = `/v1/winterns${query ? `?${query}` : ''}`
      const { data } = await api.get<WinternListResponse>(url)
      return data
    },
  })
}

// Get single Wintern
export function useWintern(id: string | undefined) {
  return useQuery({
    queryKey: id ? winternKeys.detail(id) : winternKeys.details(),
    queryFn: async () => {
      const { data } = await api.get<Wintern>(`/v1/winterns/${id}`)
      return data
    },
    enabled: !!id,
  })
}

// Create Wintern
export function useCreateWintern() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (data: WinternCreate) => {
      const { data: wintern } = await api.post<Wintern>('/v1/winterns', data)
      return wintern
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: winternKeys.lists() })
    },
  })
}

// Update Wintern
export function useUpdateWintern() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: WinternUpdate }) => {
      const { data: wintern } = await api.put<Wintern>(`/v1/winterns/${id}`, data)
      return wintern
    },
    onSuccess: (wintern) => {
      queryClient.invalidateQueries({ queryKey: winternKeys.lists() })
      queryClient.setQueryData(winternKeys.detail(wintern.id), wintern)
    },
  })
}

// Delete Wintern
export function useDeleteWintern() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/v1/winterns/${id}`)
      return id
    },
    onSuccess: (id) => {
      queryClient.invalidateQueries({ queryKey: winternKeys.lists() })
      queryClient.removeQueries({ queryKey: winternKeys.detail(id) })
    },
  })
}

// Trigger Run
export function useTriggerRun() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (winternId: string) => {
      const { data } = await api.post<TriggerRunResponse>(`/v1/winterns/${winternId}/run`)
      return data
    },
    onSuccess: (_, winternId) => {
      // Invalidate runs list to show the new pending run
      queryClient.invalidateQueries({ queryKey: winternKeys.runs(winternId) })
    },
  })
}

// List Wintern Runs
export function useWinternRuns(
  winternId: string | undefined,
  params: PaginationParams = {},
  options?: { refetchInterval?: number | false }
) {
  return useQuery({
    queryKey: winternId
      ? winternKeys.runList(winternId, params)
      : [...winternKeys.all, 'runs'] as const,
    queryFn: async () => {
      const searchParams = new URLSearchParams()
      if (params.skip !== undefined) searchParams.set('skip', String(params.skip))
      if (params.limit !== undefined) searchParams.set('limit', String(params.limit))
      const query = searchParams.toString()
      const url = `/v1/winterns/${winternId}/runs${query ? `?${query}` : ''}`
      const { data } = await api.get<WinternRunListResponse>(url)
      return data
    },
    enabled: !!winternId,
    refetchInterval: options?.refetchInterval,
  })
}

// Get single Run
export function useWinternRun(winternId: string | undefined, runId: string | undefined) {
  return useQuery({
    queryKey: winternId && runId
      ? winternKeys.run(winternId, runId)
      : [...winternKeys.all, 'run'] as const,
    queryFn: async () => {
      const { data } = await api.get<WinternRun>(`/v1/winterns/${winternId}/runs/${runId}`)
      return data
    },
    enabled: !!winternId && !!runId,
  })
}
