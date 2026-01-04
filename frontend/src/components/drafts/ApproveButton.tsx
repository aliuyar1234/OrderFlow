/**
 * Approve Button Component
 * Handles draft order approval with confirmation dialog
 * Based on spec 014-draft-orders-ui Phase 5
 */

'use client'

import React, { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { draftsApi } from '@/lib/api/drafts'
import type { DraftOrder } from '@/lib/types'

interface ApproveButtonProps {
  draftOrder: DraftOrder
  onSuccess?: () => void
}

export function ApproveButton({ draftOrder, onSuccess }: ApproveButtonProps) {
  const [showConfirmation, setShowConfirmation] = useState(false)
  const queryClient = useQueryClient()

  const approveMutation = useMutation({
    mutationFn: () => draftsApi.approve(draftOrder.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['draft-order', draftOrder.id] })
      setShowConfirmation(false)
      onSuccess?.()
    },
  })

  const isReady = draftOrder.ready_check_json?.ready
  const canApprove = draftOrder.status === 'READY' && isReady
  const blockingReasons = draftOrder.ready_check_json?.blocking_reasons || []

  const getTooltip = () => {
    if (draftOrder.status === 'APPROVED') return 'Already approved'
    if (draftOrder.status === 'PUSHED') return 'Already pushed to ERP'
    if (!isReady && blockingReasons.length > 0) {
      const displayReasons = blockingReasons.slice(0, 3)
      const tooltip = `Cannot approve: ${displayReasons.map((r, i) => `${i + 1}) ${r}`).join(', ')}`
      return blockingReasons.length > 3
        ? `${tooltip}...and ${blockingReasons.length - 3} more issues`
        : tooltip
    }
    return undefined
  }

  return (
    <>
      <button
        onClick={() => setShowConfirmation(true)}
        disabled={!canApprove || approveMutation.isPending}
        title={getTooltip()}
        className="px-4 py-2 bg-green-600 text-white rounded-md font-medium hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {approveMutation.isPending ? 'Approving...' : 'Approve'}
      </button>

      {/* Confirmation Dialog */}
      {showConfirmation && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              Confirm Approval
            </h3>
            <p className="text-sm text-gray-600 mb-6">
              Are you sure you want to approve this draft order? Once approved,
              the order will be ready to push to ERP.
            </p>

            {approveMutation.error && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md">
                <p className="text-sm text-red-800">
                  Error: {approveMutation.error.message}
                </p>
              </div>
            )}

            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowConfirmation(false)}
                disabled={approveMutation.isPending}
                className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={() => approveMutation.mutate()}
                disabled={approveMutation.isPending}
                className="px-4 py-2 bg-green-600 text-white rounded-md text-sm font-medium hover:bg-green-700 disabled:opacity-50"
              >
                {approveMutation.isPending ? 'Approving...' : 'Confirm Approval'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
