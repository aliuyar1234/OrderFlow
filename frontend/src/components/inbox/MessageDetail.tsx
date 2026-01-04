'use client';

import { InboxMessage } from '@/lib/api/inbox';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { formatDateTime } from '@/lib/utils';
import { AttachmentList } from './AttachmentList';
import { DraftOrderLink } from './DraftOrderLink';

interface MessageDetailProps {
  message: InboxMessage;
}

export function MessageDetail({ message }: MessageDetailProps) {
  return (
    <div className="space-y-6">
      {/* Header Section */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-start justify-between mb-4">
          <div className="flex-1">
            <h1 className="text-2xl font-bold text-gray-900 mb-2">
              {message.subject}
            </h1>
            <div className="flex items-center space-x-2">
              <StatusBadge status={message.status} />
              <span className="text-xs text-gray-500">
                {message.source === 'EMAIL' ? 'Email' : 'Upload'}
              </span>
            </div>
          </div>
        </div>

        {/* Message Metadata */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t border-gray-200">
          <div>
            <label className="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">
              From
            </label>
            <p className="text-sm text-gray-900">{message.from_email}</p>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">
              To
            </label>
            <p className="text-sm text-gray-900">{message.to_email}</p>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">
              Received At
            </label>
            <p className="text-sm text-gray-900">{formatDateTime(message.received_at)}</p>
          </div>

          {message.source_message_id && (
            <div>
              <label className="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">
                Message ID
              </label>
              <p className="text-sm text-gray-900 font-mono truncate" title={message.source_message_id}>
                {message.source_message_id}
              </p>
            </div>
          )}

          <div>
            <label className="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">
              Created At
            </label>
            <p className="text-sm text-gray-900">{formatDateTime(message.created_at)}</p>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">
              Message ID (Internal)
            </label>
            <p className="text-sm text-gray-900 font-mono">{message.id}</p>
          </div>
        </div>
      </div>

      {/* Attachments Section */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Attachments ({message.attachments.length})
        </h2>
        <AttachmentList attachments={message.attachments} />
      </div>

      {/* Draft Orders Section */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Draft Orders {message.draft_orders.length > 0 && `(${message.draft_orders.length})`}
        </h2>
        <DraftOrderLink drafts={message.draft_orders} />
      </div>

      {/* Processing Status Info */}
      {message.status === 'PROCESSING' && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-start">
            <div className="flex-shrink-0">
              <svg
                className="h-5 w-5 text-blue-400 animate-spin"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                ></circle>
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                ></path>
              </svg>
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-blue-800">Processing</h3>
              <p className="mt-1 text-sm text-blue-700">
                This message is currently being processed. Draft orders will appear once extraction is complete.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Failed Status Info */}
      {message.status === 'FAILED' && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-start">
            <div className="flex-shrink-0">
              <svg
                className="h-5 w-5 text-red-400"
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                  clipRule="evenodd"
                />
              </svg>
            </div>
            <div className="ml-3 flex-1">
              <h3 className="text-sm font-medium text-red-800">Processing Failed</h3>
              <p className="mt-1 text-sm text-red-700">
                There was an error processing this message. Please contact support if this issue persists.
              </p>
              <button className="mt-3 px-3 py-1.5 text-sm font-medium text-red-700 bg-red-100 rounded-md hover:bg-red-200 focus:outline-none focus:ring-2 focus:ring-red-500">
                Retry Processing
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
