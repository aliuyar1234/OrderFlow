/**
 * Line Items Table Component
 * Displays and allows editing of draft order line items
 * Based on spec 014-draft-orders-ui Phase 3
 */

'use client'

import React from 'react'
import type { DraftOrderLine, ValidationIssue } from '@/lib/types'
import { ConfidenceIndicator } from './ConfidenceIndicator'

interface LineItemsTableProps {
  lines: DraftOrderLine[]
  issues: ValidationIssue[]
  onLineUpdate?: (lineId: string, updates: Partial<DraftOrderLine>) => void
  onLineDelete?: (lineId: string) => void
  readOnly?: boolean
}

export function LineItemsTable({
  lines,
  issues,
  onLineUpdate,
  onLineDelete,
  readOnly = false,
}: LineItemsTableProps) {
  // Group issues by line
  const issuesByLine = React.useMemo(() => {
    const map = new Map<string, ValidationIssue[]>()
    issues.forEach((issue) => {
      if (issue.draft_order_line_id) {
        const existing = map.get(issue.draft_order_line_id) || []
        map.set(issue.draft_order_line_id, [...existing, issue])
      }
    })
    return map
  }, [issues])

  const getLineIssues = (lineId: string) => issuesByLine.get(lineId) || []

  const getLineSeverityClass = (lineId: string) => {
    const lineIssues = getLineIssues(lineId)
    const hasError = lineIssues.some((i) => i.severity === 'ERROR' && i.status === 'OPEN')
    const hasWarning = lineIssues.some((i) => i.severity === 'WARNING' && i.status === 'OPEN')

    if (hasError) return 'bg-red-50 border-l-4 border-red-500'
    if (hasWarning) return 'bg-yellow-50 border-l-4 border-yellow-500'
    return ''
  }

  const renderIssueBadge = (lineId: string) => {
    const lineIssues = getLineIssues(lineId).filter((i) => i.status === 'OPEN')
    if (lineIssues.length === 0) return null

    const hasError = lineIssues.some((i) => i.severity === 'ERROR')
    const badgeClass = hasError
      ? 'bg-red-100 text-red-800 border-red-300'
      : 'bg-yellow-100 text-yellow-800 border-yellow-300'

    return (
      <span
        className={`inline-flex items-center px-2 py-1 rounded-md text-xs font-medium border ${badgeClass}`}
        title={lineIssues.map((i) => i.message).join('; ')}
      >
        {lineIssues.length} issue{lineIssues.length > 1 ? 's' : ''}
      </span>
    )
  }

  if (lines.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500">
        No line items found
      </div>
    )
  }

  return (
    <div className="overflow-x-auto border border-gray-200 rounded-lg">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase w-12">
              #
            </th>
            <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">
              Customer SKU
            </th>
            <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">
              Description
            </th>
            <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase w-20">
              Qty
            </th>
            <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase w-16">
              UoM
            </th>
            <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase w-24">
              Price
            </th>
            <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">
              Internal SKU
            </th>
            <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase w-32">
              Match
            </th>
            <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase w-24">
              Issues
            </th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {lines.map((line) => (
            <tr key={line.id} className={getLineSeverityClass(line.id)}>
              <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-500">
                {line.line_no}
              </td>
              <td className="px-3 py-4 text-sm text-gray-900">
                {line.customer_sku_raw || (
                  <span className="text-gray-400 italic">—</span>
                )}
              </td>
              <td className="px-3 py-4 text-sm text-gray-900 max-w-xs">
                <div className="line-clamp-2">
                  {line.product_description || (
                    <span className="text-gray-400 italic">—</span>
                  )}
                </div>
              </td>
              <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-900">
                {line.qty !== null ? line.qty : (
                  <span className="text-gray-400 italic">—</span>
                )}
              </td>
              <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-900">
                {line.uom || <span className="text-gray-400 italic">—</span>}
              </td>
              <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-900">
                {line.unit_price !== null ? (
                  `${line.currency} ${line.unit_price.toFixed(2)}`
                ) : (
                  <span className="text-gray-400 italic">—</span>
                )}
              </td>
              <td className="px-3 py-4 text-sm">
                {line.internal_sku ? (
                  <div className="flex items-center gap-1">
                    <span className="font-mono text-sm">{line.internal_sku}</span>
                    {line.match_status === 'SUGGESTED' && (
                      <span className="text-xs text-blue-600">(suggested)</span>
                    )}
                    {line.match_status === 'CONFIRMED' && (
                      <span className="text-xs text-green-600">✓</span>
                    )}
                  </div>
                ) : (
                  <span className="text-red-500 text-xs">No match</span>
                )}
              </td>
              <td className="px-3 py-4 whitespace-nowrap">
                {line.matching_confidence > 0 && (
                  <div className="w-24">
                    <ConfidenceIndicator
                      score={line.matching_confidence}
                      showPercentage={false}
                    />
                  </div>
                )}
              </td>
              <td className="px-3 py-4 whitespace-nowrap">
                {renderIssueBadge(line.id)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
