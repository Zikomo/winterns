import { useQuery } from '@tanstack/react-query'
import { checkHealth } from '@/lib/api'

export function HealthPage() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['health'],
    queryFn: checkHealth,
    refetchInterval: 10000, // Refetch every 10 seconds
  })

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="bg-white rounded-lg shadow-md p-8 max-w-md w-full">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">
          System Health Check
        </h1>

        {isLoading && (
          <div className="flex items-center space-x-2">
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600" />
            <span className="text-gray-600">Checking backend status...</span>
          </div>
        )}

        {isError && (
          <div className="bg-red-50 border border-red-200 rounded-md p-4">
            <div className="flex items-center space-x-2">
              <span className="text-red-600 text-xl">✗</span>
              <div>
                <p className="font-medium text-red-800">Backend Unavailable</p>
                <p className="text-sm text-red-600">
                  {error instanceof Error ? error.message : 'Connection failed'}
                </p>
              </div>
            </div>
          </div>
        )}

        {data && (
          <div className="bg-green-50 border border-green-200 rounded-md p-4">
            <div className="flex items-center space-x-2">
              <span className="text-green-600 text-xl">✓</span>
              <div>
                <p className="font-medium text-green-800">Backend Online</p>
                <p className="text-sm text-green-600">
                  Status: {data.status}
                </p>
              </div>
            </div>
          </div>
        )}

        <div className="mt-6 text-sm text-gray-500">
          <p>Frontend: React + Vite</p>
          <p>Auto-refreshing every 10 seconds</p>
        </div>
      </div>
    </div>
  )
}
