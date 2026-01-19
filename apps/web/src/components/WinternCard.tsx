import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { useTriggerRun, useDeleteWintern } from '@/lib/queries'
import { formatDate, parseFrequency, formatRelativeTime } from '@/lib/utils'
import type { Wintern } from '@/types'

export interface WinternCardProps {
  wintern: Wintern
}

export function WinternCard({ wintern }: WinternCardProps) {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const triggerRun = useTriggerRun()
  const deleteWintern = useDeleteWintern()

  const frequency = parseFrequency(wintern.cronSchedule)

  const handleRunNow = () => {
    triggerRun.mutate(wintern.id)
  }

  const handleDelete = () => {
    deleteWintern.mutate(wintern.id, {
      onSuccess: () => {
        setShowDeleteConfirm(false)
      },
    })
  }

  return (
    <Card className="flex flex-col hover:shadow-md transition-shadow">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-lg text-gray-900 truncate">
            {wintern.name}
          </h3>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <Badge
            variant={wintern.isActive ? 'success' : 'default'}
            size="sm"
          >
            {wintern.isActive ? 'Active' : 'Paused'}
          </Badge>
          <Badge variant="info" size="sm">
            {frequency}
          </Badge>
        </div>
      </div>

      {/* Context preview */}
      <p className="mt-2 text-sm text-gray-600 line-clamp-2">
        {wintern.context}
      </p>

      {/* Schedule info */}
      <div className="mt-4 flex flex-col gap-1 text-xs text-gray-500">
        <div className="flex items-center gap-2">
          <span className="font-medium">Next run:</span>
          <span>{formatRelativeTime(wintern.nextRunAt)}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-medium">Created:</span>
          <span>{formatDate(wintern.createdAt)}</span>
        </div>
      </div>

      {/* Actions */}
      <div className="mt-auto pt-4 flex items-center gap-2">
        {showDeleteConfirm ? (
          <>
            <span className="text-sm text-gray-600">Delete?</span>
            <Button
              variant="danger"
              size="sm"
              onClick={handleDelete}
              loading={deleteWintern.isPending}
            >
              Yes
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setShowDeleteConfirm(false)}
            >
              No
            </Button>
          </>
        ) : (
          <>
            <Link to={`/winterns/${wintern.id}`}>
              <Button variant="secondary" size="sm">
                Edit
              </Button>
            </Link>
            <Button
              variant="primary"
              size="sm"
              onClick={handleRunNow}
              loading={triggerRun.isPending}
              disabled={!wintern.isActive}
            >
              Run Now
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowDeleteConfirm(true)}
              className="ml-auto text-gray-500 hover:text-red-600"
            >
              Delete
            </Button>
          </>
        )}
      </div>
    </Card>
  )
}
