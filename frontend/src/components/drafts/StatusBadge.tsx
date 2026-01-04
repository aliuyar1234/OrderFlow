/**
 * Status badge component for draft orders
 * Displays status with appropriate color coding
 */

import React from 'react'
import type { DraftOrderStatus } from '@/lib/types'

interface StatusBadgeProps {
  status: DraftOrderStatus
  className?: string
}

const statusConfig: Record<
  DraftOrderStatus,
  { label: string; className: string }
> = {
  NEW: {
    label: 'New',
    className: 'bg-gray-100 text-gray-800 border-gray-300',
  },
  EXTRACTED: {
    label: 'Extracted',
    className: 'bg-blue-100 text-blue-800 border-blue-300',
  },
  NEEDS_REVIEW: {
    label: 'Needs Review',
    className: 'bg-yellow-100 text-yellow-800 border-yellow-300',
  },
  READY: {
    label: 'Ready',
    className: 'bg-green-100 text-green-800 border-green-300',
  },
  APPROVED: {
    label: 'Approved',
    className: 'bg-purple-100 text-purple-800 border-purple-300',
  },
  PUSHING: {
    label: 'Pushing',
    className: 'bg-indigo-100 text-indigo-800 border-indigo-300',
  },
  PUSHED: {
    label: 'Pushed',
    className: 'bg-emerald-100 text-emerald-800 border-emerald-300',
  },
  ERROR: {
    label: 'Error',
    className: 'bg-red-100 text-red-800 border-red-300',
  },
}

export function StatusBadge({ status, className = '' }: StatusBadgeProps) {
  const config = statusConfig[status]

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${config.className} ${className}`}
    >
      {config.label}
    </span>
  )
}
