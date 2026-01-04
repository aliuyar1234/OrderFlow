'use client';

import { useParams, useRouter } from 'next/navigation';
import { MessageDetail } from '@/components/inbox/MessageDetail';
import { useInboxMessage } from '@/lib/hooks/useInbox';

export default function InboxMessagePage() {
  const params = useParams();
  const router = useRouter();
  const messageId = params.id as string;

  const { data: message, isLoading, error } = useInboxMessage(messageId);

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-blue-600 border-r-transparent"></div>
          <p className="mt-4 text-gray-600">Loading message...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
          <svg
            className="mx-auto h-12 w-12 text-red-500 mb-4"
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
          <h2 className="text-xl font-semibold text-gray-900 mb-2">
            Message not found
          </h2>
          <p className="text-gray-600 mb-6">
            The message you're looking for doesn't exist or you don't have permission to view it.
          </p>
          <button
            onClick={() => router.push('/inbox')}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
          >
            Back to Inbox
          </button>
        </div>
      </div>
    );
  }

  if (!message) {
    return null;
  }

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Breadcrumb */}
      <nav className="mb-6">
        <ol className="flex items-center space-x-2 text-sm">
          <li>
            <button
              onClick={() => router.push('/inbox')}
              className="text-blue-600 hover:text-blue-800 font-medium"
            >
              Inbox
            </button>
          </li>
          <li className="text-gray-400">/</li>
          <li className="text-gray-600">Message Details</li>
        </ol>
      </nav>

      <MessageDetail message={message} />
    </div>
  );
}
