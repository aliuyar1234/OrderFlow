/**
 * Draft Orders Table Component
 * Displays paginated list of draft orders with filtering and sorting
 * Based on spec 014-draft-orders-ui Phase 2
 */

'use client'

import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import { draftsApi } from '@/lib/api/drafts'
import { StatusBadge } from './StatusBadge'
import { ConfidenceIndicator } from './ConfidenceIndicator'
import type { DraftOrderStatus } from '@/lib/types'

export function DraftOrdersTable() {
  const router = useRouter()
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [page, setPage] = useState(1)
  const pageSize = 25

  const { data, isLoading, error } = useQuery({
    queryKey: ['draft-orders', { status: statusFilter, page, size: pageSize }],
    queryFn: () =>
      draftsApi.list({
        status: statusFilter || undefined,
        page,
        size: pageSize,
        sort: '-created_at',
      }),
  })

  const handleRowClick = (draftId: string) => {
    router.push(`/drafts/${draftId}`)
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading draft orders...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-red-500">
          Error loading draft orders: {error.message}
        </div>
      </div>
    )
  }

  const drafts = data?.items || []
  const totalPages = data?.pages || 1

  return (
    <div className="space-y-4">
      {/* Filter Controls */}
      <div className="flex items-center gap-4">
        <label htmlFor="status-filter" className="text-sm font-medium text-gray-700">
          Filter by Status:
        </label>
        <select
          id="status-filter"
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value)
            setPage(1) // Reset to first page
          }}
          className="px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        >
          <option value="">All Statuses</option>
          <option value="NEEDS_REVIEW">Needs Review</option>
          <option value="READY">Ready</option>
          <option value="APPROVED">Approved</option>
          <option value="PUSHED">Pushed</option>
          <option value="ERROR">Error</option>
        </select>

        <div className="ml-auto text-sm text-gray-600">
          {data?.total || 0} total orders
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto border border-gray-200 rounded-lg">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Order Number
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Customer
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Status
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Lines
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Confidence
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Created
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {drafts.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-6 py-8 text-center text-gray-500">
                  No draft orders found
                </td>
              </tr>
            ) : (
              drafts.map((draft) => (
                <tr
                  key={draft.id}
                  onClick={() => handleRowClick(draft.id)}
                  className="hover:bg-gray-50 cursor-pointer transition-colors"
                >
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    {draft.external_order_number || (
                      <span className="text-gray-400 italic">No order number</span>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {draft.customer_name || (
                      <span className="text-gray-400 italic">Unknown</span>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <StatusBadge status={draft.status as DraftOrderStatus} />
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {draft.line_count}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="w-32">
                      <ConfidenceIndicator score={draft.confidence_score} />
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {new Date(draft.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Previous
          </button>

          <span className="text-sm text-gray-700">
            Page {page} of {totalPages}
          </span>

          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}
