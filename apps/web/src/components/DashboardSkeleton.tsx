import { Card } from '@/components/ui/Card'
import { Skeleton, SkeletonText } from '@/components/ui/Skeleton'

function WinternCardSkeleton() {
  return (
    <Card className="flex flex-col">
      {/* Header with name and badges */}
      <div className="flex items-start justify-between gap-2">
        <Skeleton variant="text" className="h-6 w-32" />
        <div className="flex items-center gap-2">
          <Skeleton variant="rectangular" className="h-5 w-14 rounded-full" />
          <Skeleton variant="rectangular" className="h-5 w-14 rounded-full" />
        </div>
      </div>

      {/* Context preview */}
      <div className="mt-2">
        <SkeletonText lines={2} />
      </div>

      {/* Schedule info */}
      <div className="mt-4 space-y-1">
        <Skeleton variant="text" className="h-3 w-24" />
        <Skeleton variant="text" className="h-3 w-28" />
      </div>

      {/* Actions */}
      <div className="mt-auto pt-4 flex items-center gap-2">
        <Skeleton variant="rectangular" className="h-8 w-14 rounded-md" />
        <Skeleton variant="rectangular" className="h-8 w-20 rounded-md" />
        <Skeleton variant="rectangular" className="h-8 w-14 ml-auto rounded-md" />
      </div>
    </Card>
  )
}

export interface DashboardSkeletonProps {
  count?: number
}

export function DashboardSkeleton({ count = 6 }: DashboardSkeletonProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {Array.from({ length: count }).map((_, index) => (
        <WinternCardSkeleton key={index} />
      ))}
    </div>
  )
}
