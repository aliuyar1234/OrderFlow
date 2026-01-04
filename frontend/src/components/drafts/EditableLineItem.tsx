/**
 * Editable Line Item Component
 * Provides inline editing for draft order line items
 * Based on spec 014-draft-orders-ui Phase 4
 */

'use client'

import React, { useState } from 'react'
import type { DraftOrderLine } from '@/lib/types'
import { useUpdateLineItem, useConfirmMapping } from '@/lib/hooks/useDraftMutations'

interface EditableLineItemProps {
  line: DraftOrderLine
  draftId: string
}

export function EditableLineItem({ line, draftId }: EditableLineItemProps) {
  const [isEditing, setIsEditing] = useState<string | null>(null)
  const [editValues, setEditValues] = useState<Partial<DraftOrderLine>>({})

  const updateMutation = useUpdateLineItem(draftId)
  const confirmMappingMutation = useConfirmMapping(draftId)

  const startEditing = (field: string, value: any) => {
    setIsEditing(field)
    setEditValues({ [field]: value })
  }

  const cancelEditing = () => {
    setIsEditing(null)
    setEditValues({})
  }

  const saveEdit = async (field: string) => {
    if (editValues[field as keyof DraftOrderLine] !== undefined) {
      try {
        await updateMutation.mutateAsync({
          draftId,
          lineId: line.id,
          [field]: editValues[field as keyof DraftOrderLine],
        })
        setIsEditing(null)
        setEditValues({})
      } catch (error) {
        console.error('Failed to update line item:', error)
      }
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent, field: string) => {
    if (e.key === 'Enter') {
      saveEdit(field)
    } else if (e.key === 'Escape') {
      cancelEditing()
    }
  }

  const renderEditableField = (
    field: keyof DraftOrderLine,
    displayValue: any,
    type: 'text' | 'number' = 'text'
  ) => {
    if (isEditing === field) {
      return (
        <input
          type={type}
          value={editValues[field] ?? ''}
          onChange={(e) =>
            setEditValues({
              ...editValues,
              [field]: type === 'number' ? Number(e.target.value) : e.target.value,
            })
          }
          onKeyDown={(e) => handleKeyDown(e, field)}
          onBlur={() => saveEdit(field)}
          autoFocus
          className="w-full px-2 py-1 border border-blue-500 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      )
    }

    return (
      <span
        onClick={() => startEditing(field, line[field])}
        className="cursor-pointer hover:bg-gray-100 px-2 py-1 rounded"
      >
        {displayValue || <span className="text-gray-400 italic">—</span>}
      </span>
    )
  }

  return (
    <tr className="hover:bg-gray-50">
      <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-500">
        {line.line_no}
      </td>
      <td className="px-3 py-4 text-sm text-gray-900">
        {renderEditableField('customer_sku_raw', line.customer_sku_raw)}
      </td>
      <td className="px-3 py-4 text-sm text-gray-900">
        {renderEditableField('product_description', line.product_description)}
      </td>
      <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-900">
        {renderEditableField('qty', line.qty, 'number')}
      </td>
      <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-900">
        {renderEditableField('uom', line.uom)}
      </td>
      <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-900">
        {renderEditableField('unit_price', line.unit_price, 'number')}
      </td>
      <td className="px-3 py-4 text-sm">
        <div className="flex items-center gap-2">
          {line.internal_sku ? (
            <>
              <span className="font-mono text-sm">{line.internal_sku}</span>
              {line.match_status === 'SUGGESTED' && (
                <button
                  onClick={() => confirmMappingMutation.mutate(line.id)}
                  disabled={confirmMappingMutation.isPending}
                  className="text-xs px-2 py-1 bg-blue-100 text-blue-700 rounded hover:bg-blue-200 disabled:opacity-50"
                >
                  Confirm
                </button>
              )}
              {line.match_status === 'CONFIRMED' && (
                <span className="text-xs text-green-600">✓ Confirmed</span>
              )}
            </>
          ) : (
            <span className="text-red-500 text-xs">No match</span>
          )}
        </div>
      </td>
    </tr>
  )
}
