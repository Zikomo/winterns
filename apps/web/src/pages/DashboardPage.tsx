import { Link } from 'react-router-dom'
import { useWinterns } from '@/lib/queries'
import { WinternCard } from '@/components/WinternCard'
import { DashboardSkeleton } from '@/components/DashboardSkeleton'
import { EmptyState, EmptyStateIcon } from '@/components/ui/EmptyState'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'

export function DashboardPage() {
  const { data, isLoading, isError, error, refetch } = useWinterns()

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
            <p className="text-gray-600 mt-1">
              Manage your AI research agents
            </p>
          </div>
          <Link to="/winterns/new">
            <Button variant="primary">Create Wintern</Button>
          </Link>
        </div>

        {/* Content */}
        {isLoading ? (
          <DashboardSkeleton count={6} />
        ) : isError ? (
          <Card className="max-w-md mx-auto">
            <div className="text-center py-8">
              <h3 className="text-lg font-medium text-gray-900 mb-2">
                Failed to load winterns
              </h3>
              <p className="text-sm text-gray-500 mb-4">
                {error instanceof Error ? error.message : 'An unexpected error occurred'}
              </p>
              <Button variant="primary" onClick={() => refetch()}>
                Try Again
              </Button>
            </div>
          </Card>
        ) : !data?.items?.length ? (
          <EmptyState
            icon={<EmptyStateIcon />}
            title="No Winterns yet"
            description="Create your first Wintern to start monitoring the web for content that matters to you."
            action={
              <Link to="/winterns/new">
                <Button variant="primary">Create Wintern</Button>
              </Link>
            }
          />
        ) : (
          <>
            {/* Stats summary - only show if API provides aggregate counts or all items fit on one page */}
            {(data.activeCount !== undefined || data.items.length === data.total) && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                <Card padding="sm" className="text-center">
                  <div className="text-2xl font-bold text-gray-900">
                    {data.total}
                  </div>
                  <div className="text-sm text-gray-500">Total Winterns</div>
                </Card>
                <Card padding="sm" className="text-center">
                  <div className="text-2xl font-bold text-green-600">
                    {data.activeCount ?? data.items.filter((w) => w.isActive).length}
                  </div>
                  <div className="text-sm text-gray-500">Active</div>
                </Card>
                <Card padding="sm" className="text-center">
                  <div className="text-2xl font-bold text-gray-400">
                    {data.pausedCount ?? data.items.filter((w) => !w.isActive).length}
                  </div>
                  <div className="text-sm text-gray-500">Paused</div>
                </Card>
                <Card padding="sm" className="text-center">
                  <div className="text-2xl font-bold text-blue-600">
                    {data.scheduledCount ?? data.items.filter((w) => w.nextRunAt).length}
                  </div>
                  <div className="text-sm text-gray-500">Scheduled</div>
                </Card>
              </div>
            )}

            {/* Wintern grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {data.items.map((wintern) => (
                <WinternCard key={wintern.id} wintern={wintern} />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
