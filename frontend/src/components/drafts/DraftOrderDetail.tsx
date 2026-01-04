/**
 * Draft Order Detail Component
 * Displays complete draft order information with header and lines
 * Based on spec 014-draft-orders-ui Phase 3
 */

'use client'

import React from 'react'
import type { DraftOrderDetail as DraftOrderDetailType } from '@/lib/draft-orders-types'
import { StatusBadge } from './StatusBadge'
import { ConfidenceBreakdown } from './ConfidenceIndicator'
import { LineItemsTable } from './LineItemsTable'

interface DraftOrderDetailProps {
  data: DraftOrderDetailType
  onUpdate?: () => void
}

export function DraftOrderDetail({ data, onUpdate }: DraftOrderDetailProps) {
  const { draft_order, lines, issues, customer_candidates, confidence } = data

  const formatDate = (dateString: string | null) => {
    if (!dateString) return '—'
    return new Date(dateString).toLocaleDateString()
  }

  // Count issues by severity
  const issueStats = React.useMemo(() => {
    const stats = { ERROR: 0, WARNING: 0, INFO: 0 }
    issues.filter((i) => i.status === 'OPEN').forEach((issue) => {
      stats[issue.severity]++
    })
    return stats
  }, [issues])

  return (
    <div className="space-y-6">
      {/* Header Section */}
      <div className="bg-white shadow rounded-lg p-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">
              {draft_order.external_order_number || 'Draft Order'}
            </h2>
            <p className="text-sm text-gray-500 mt-1">
              ID: {draft_order.id}
            </p>
          </div>
          <StatusBadge status={draft_order.status} />
        </div>

        <div className="grid grid-cols-2 gap-6">
          <div>
            <h3 className="text-sm font-medium text-gray-500 mb-3">
              Order Information
            </h3>
            <dl className="space-y-2">
              <div className="flex justify-between">
                <dt className="text-sm text-gray-600">Order Number:</dt>
                <dd className="text-sm font-medium text-gray-900">
                  {draft_order.external_order_number || '—'}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-sm text-gray-600">Order Date:</dt>
                <dd className="text-sm font-medium text-gray-900">
                  {formatDate(draft_order.order_date)}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-sm text-gray-600">Currency:</dt>
                <dd className="text-sm font-medium text-gray-900">
                  {draft_order.currency}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-sm text-gray-600">Delivery Date:</dt>
                <dd className="text-sm font-medium text-gray-900">
                  {formatDate(draft_order.requested_delivery_date)}
                </dd>
              </div>
            </dl>
          </div>

          <div>
            <h3 className="text-sm font-medium text-gray-500 mb-3">
              Confidence Scores
            </h3>
            <ConfidenceBreakdown
              overall={confidence.overall}
              extraction={confidence.extraction}
              customer={confidence.customer}
              matching={confidence.matching}
            />
          </div>
        </div>

        {/* Customer Section */}
        {draft_order.customer_id ? (
          <div className="mt-4 pt-4 border-t border-gray-200">
            <h3 className="text-sm font-medium text-gray-500 mb-2">
              Customer
            </h3>
            <p className="text-sm font-medium text-gray-900">
              Customer ID: {draft_order.customer_id}
            </p>
          </div>
        ) : customer_candidates.length > 0 ? (
          <div className="mt-4 pt-4 border-t border-gray-200">
            <h3 className="text-sm font-medium text-yellow-700 mb-2">
              Customer Detection Required
            </h3>
            <p className="text-sm text-gray-600 mb-3">
              Multiple customer candidates found. Please select the correct customer:
            </p>
            <div className="space-y-2">
              {customer_candidates.slice(0, 3).map((candidate) => (
                <div
                  key={candidate.customer_id}
                  className="flex items-center justify-between p-2 border border-gray-200 rounded"
                >
                  <span className="text-sm font-medium">
                    {candidate.customer_name}
                  </span>
                  <span className="text-sm text-gray-600">
                    {Math.round(candidate.score * 100)}% match
                  </span>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {/* Issues Summary */}
        {(issueStats.ERROR > 0 || issueStats.WARNING > 0) && (
          <div className="mt-4 pt-4 border-t border-gray-200">
            <h3 className="text-sm font-medium text-gray-500 mb-2">
              Validation Issues
            </h3>
            <div className="flex gap-4">
              {issueStats.ERROR > 0 && (
                <span className="inline-flex items-center px-3 py-1 rounded-md text-sm font-medium bg-red-100 text-red-800">
                  {issueStats.ERROR} Error{issueStats.ERROR > 1 ? 's' : ''}
                </span>
              )}
              {issueStats.WARNING > 0 && (
                <span className="inline-flex items-center px-3 py-1 rounded-md text-sm font-medium bg-yellow-100 text-yellow-800">
                  {issueStats.WARNING} Warning{issueStats.WARNING > 1 ? 's' : ''}
                </span>
              )}
            </div>
          </div>
        )}

        {/* Notes */}
        {draft_order.notes && (
          <div className="mt-4 pt-4 border-t border-gray-200">
            <h3 className="text-sm font-medium text-gray-500 mb-2">Notes</h3>
            <p className="text-sm text-gray-700">{draft_order.notes}</p>
          </div>
        )}
      </div>

      {/* Line Items Section */}
      <div className="bg-white shadow rounded-lg p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          Line Items ({lines.length})
        </h3>
        <LineItemsTable lines={lines} issues={issues} />
      </div>
    </div>
  )
}
