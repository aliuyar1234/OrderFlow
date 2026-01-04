'use client';

import Link from 'next/link';
import { DraftOrderSummary } from '@/lib/api/inbox';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { formatDateTime } from '@/lib/utils';

interface DraftOrderLinkProps {
  drafts: DraftOrderSummary[];
}

export function DraftOrderLink({ drafts }: DraftOrderLinkProps) {
  if (drafts.length === 0) {
    return (
      <div className="bg-gray-50 rounded-lg p-6 text-center">
        <svg
          className="mx-auto h-12 w-12 text-gray-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
          />
        </svg>
        <p className="mt-2 text-sm text-gray-600">No draft orders created yet</p>
        <p className="text-xs text-gray-500 mt-1">
          Draft orders will appear here once processing is complete
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {drafts.map((draft) => (
        <div
          key={draft.id}
          className="bg-white border border-gray-200 rounded-lg p-4 hover:border-gray-300 transition-colors"
        >
          <div className="flex items-start justify-between">
            <div className="flex-1 min-w-0">
              <div className="flex items-center space-x-2 mb-2">
                <h4 className="text-sm font-semibold text-gray-900">
                  {draft.customer_name || 'Unknown Customer'}
                </h4>
                <StatusBadge status={draft.status as any} />
              </div>
              <div className="text-xs text-gray-600 space-y-1">
                <p>
                  <span className="font-medium">{draft.line_count}</span>{' '}
                  {draft.line_count === 1 ? 'line item' : 'line items'}
                </p>
                <p className="text-gray-500">
                  Created {formatDateTime(draft.created_at)}
                </p>
              </div>
            </div>

            <Link
              href={`/drafts/${draft.id}`}
              className="ml-4 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
            >
              View Draft
            </Link>
          </div>
        </div>
      ))}

      {drafts.length > 1 && (
        <p className="text-xs text-gray-500 text-center mt-2">
          Multiple draft orders created from this message
        </p>
      )}
    </div>
  );
}
