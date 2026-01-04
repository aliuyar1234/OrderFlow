/**
 * Draft Orders List Page
 * Main page for viewing all draft orders
 * Based on spec 014-draft-orders-ui Phase 2
 */

import React from 'react'
import { DraftOrdersTable } from '@/components/drafts/DraftOrdersTable'

export default function DraftsPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Draft Orders</h1>
        <p className="mt-2 text-sm text-gray-600">
          Review and approve extracted orders before pushing to ERP
        </p>
      </div>

      <DraftOrdersTable />
    </div>
  )
}
