'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { InboxFilters } from './InboxFilters';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { useInboxMessages } from '@/lib/hooks/useInbox';
import { InboxFilters as FilterType } from '@/lib/api/inbox';
import { formatDate, truncate } from '@/lib/utils';
import Link from 'next/link';

export function InboxTable() {
  const router = useRouter();
  const [filters, setFilters] = useState<FilterType>({});
  const [cursor, setCursor] = useState<string | null>(null);

  const { data, isLoading, error, refetch } = useInboxMessages({
    ...filters,
    cursor,
    limit: 50,
  });

  const handleRowClick = (id: string) => {
    router.push(`/inbox/${id}`);
  };

  if (error) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-8 text-center">
        <div className="text-red-600 mb-4">
          <svg
            className="mx-auto h-12 w-12"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        </div>
        <h3 className="text-lg font-semibold text-gray-900 mb-2">
          Unable to load inbox
        </h3>
        <p className="text-gray-600 mb-4">
          There was a problem loading your messages. Please try again.
        </p>
        <button
          onClick={() => refetch()}
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <InboxFilters filters={filters} onChange={setFilters} />

      {isLoading && !data ? (
        <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-blue-600 border-r-transparent"></div>
          <p className="mt-4 text-gray-600">Loading messages...</p>
        </div>
      ) : data && data.items.length === 0 ? (
        <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
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
              d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
            />
          </svg>
          <h3 className="mt-4 text-lg font-semibold text-gray-900">No messages yet</h3>
          <p className="mt-2 text-gray-600">
            {filters.status || filters.from_email || filters.q
              ? 'No messages match your filters. Try adjusting your search criteria.'
              : 'Your inbox is empty. Messages will appear here when received.'}
          </p>
        </div>
      ) : (
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Received
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    From
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Subject
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Attachments
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Draft
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {data?.items.map((item) => (
                  <tr
                    key={item.id}
                    onClick={() => handleRowClick(item.id)}
                    className="hover:bg-gray-50 cursor-pointer transition-colors"
                  >
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {formatDate(item.received_at)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      <div className="max-w-xs" title={item.from_email}>
                        {truncate(item.from_email, 30)}
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900">
                      <div className="max-w-md" title={item.subject}>
                        {truncate(item.subject, 60)}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                        {item.attachment_count}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      <StatusBadge status={item.status} />
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      {item.draft_order_ids.length > 0 ? (
                        <Link
                          href={`/drafts/${item.draft_order_ids[0]}`}
                          onClick={(e) => e.stopPropagation()}
                          className="text-blue-600 hover:text-blue-800 font-medium"
                        >
                          View Draft
                        </Link>
                      ) : item.status === 'PROCESSING' ? (
                        <span className="text-gray-500 text-xs">Processing...</span>
                      ) : item.status === 'FAILED' ? (
                        <span className="text-red-600 text-xs">Failed</span>
                      ) : (
                        <span className="text-gray-400 text-xs">-</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {data?.next_cursor && (
            <div className="px-6 py-4 border-t border-gray-200 bg-gray-50">
              <button
                onClick={() => setCursor(data.next_cursor)}
                className="w-full px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
              >
                Load More
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
