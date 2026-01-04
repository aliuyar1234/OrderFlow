/**
 * Draft Order Detail Page
 * Dynamic route for individual draft order details
 * Based on spec 014-draft-orders-ui Phase 3
 */

'use client'

import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { draftsApi } from '@/lib/api/drafts'
import { DraftOrderDetail } from '@/components/drafts/DraftOrderDetail'
import { ApproveButton } from '@/components/drafts/ApproveButton'

interface PageProps {
  params: {
    id: string
  }
}

export default function DraftDetailPage({ params }: PageProps) {
  const router = useRouter()
  const { data, isLoading, error } = useQuery({
    queryKey: ['draft-order', params.id],
    queryFn: () => draftsApi.getDetail(params.id),
  })

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-center justify-center h-64">
          <div className="text-gray-500">Loading draft order...</div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-center justify-center h-64">
          <div className="text-red-500">
            Error loading draft order: {error.message}
          </div>
        </div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-center justify-center h-64">
          <div className="text-gray-500">Draft order not found</div>
        </div>
      </div>
    )
  }

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Breadcrumbs */}
      <nav className="flex mb-6" aria-label="Breadcrumb">
        <ol className="inline-flex items-center space-x-1 md:space-x-3">
          <li className="inline-flex items-center">
            <Link
              href="/drafts"
              className="text-sm text-gray-700 hover:text-gray-900"
            >
              Draft Orders
            </Link>
          </li>
          <li>
            <div className="flex items-center">
              <span className="mx-2 text-gray-400">/</span>
              <span className="text-sm text-gray-500">
                {data.draft_order.external_order_number || 'Detail'}
              </span>
            </div>
          </li>
        </ol>
      </nav>

      {/* Action Bar */}
      <div className="flex items-center justify-between mb-6">
        <button
          onClick={() => router.back()}
          className="text-sm text-gray-600 hover:text-gray-900"
        >
          ← Back
        </button>

        <div className="flex gap-3">
          {data.draft_order.status === 'READY' && (
            <ApproveButton
              draftOrder={data.draft_order}
              onSuccess={() => {
                // Optionally navigate to next draft or show success message
              }}
            />
          )}

          {data.draft_order.status === 'APPROVED' && (
            <button
              onClick={() => {
                // TODO: Implement push to ERP
                console.log('Push to ERP')
              }}
              className="px-4 py-2 bg-blue-600 text-white rounded-md font-medium hover:bg-blue-700"
            >
              Push to ERP
            </button>
          )}

          {data.draft_order.document_id && (
            <Link
              href={`/documents/${data.draft_order.document_id}`}
              className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              View Source Document
            </Link>
          )}
        </div>
      </div>

      {/* Main Content */}
      <DraftOrderDetail data={data} />
    </div>
  )
}
