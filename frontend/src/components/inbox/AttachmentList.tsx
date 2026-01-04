'use client';

import { useState } from 'react';
import { DocumentAttachment } from '@/lib/api/inbox';
import { formatFileSize } from '@/lib/utils';
import { AttachmentPreview } from './AttachmentPreview';

interface AttachmentListProps {
  attachments: DocumentAttachment[];
}

export function AttachmentList({ attachments }: AttachmentListProps) {
  const [previewDocumentId, setPreviewDocumentId] = useState<string | null>(null);

  if (attachments.length === 0) {
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
        <p className="mt-2 text-sm text-gray-600">No attachments</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {attachments.map((attachment) => (
        <div
          key={attachment.document_id}
          className="bg-white border border-gray-200 rounded-lg p-4 hover:border-gray-300 transition-colors"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3 flex-1 min-w-0">
              {/* File Icon */}
              <div className="flex-shrink-0">
                {attachment.mime_type === 'application/pdf' ? (
                  <svg
                    className="h-10 w-10 text-red-500"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fillRule="evenodd"
                      d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z"
                      clipRule="evenodd"
                    />
                  </svg>
                ) : attachment.mime_type.startsWith('application/vnd.ms-excel') ||
                  attachment.mime_type.startsWith('application/vnd.openxmlformats-officedocument.spreadsheetml') ? (
                  <svg
                    className="h-10 w-10 text-green-500"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fillRule="evenodd"
                      d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z"
                      clipRule="evenodd"
                    />
                  </svg>
                ) : (
                  <svg
                    className="h-10 w-10 text-gray-400"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fillRule="evenodd"
                      d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z"
                      clipRule="evenodd"
                    />
                  </svg>
                )}
              </div>

              {/* File Info */}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate" title={attachment.file_name}>
                  {attachment.file_name}
                </p>
                <div className="flex items-center space-x-2 mt-1">
                  <p className="text-xs text-gray-500">
                    {formatFileSize(attachment.size_bytes)}
                  </p>
                  {attachment.page_count && (
                    <>
                      <span className="text-gray-300">•</span>
                      <p className="text-xs text-gray-500">
                        {attachment.page_count} {attachment.page_count === 1 ? 'page' : 'pages'}
                      </p>
                    </>
                  )}
                  {attachment.status && (
                    <>
                      <span className="text-gray-300">•</span>
                      <span className="text-xs text-gray-600 font-medium">
                        {attachment.status}
                      </span>
                    </>
                  )}
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center space-x-2 ml-4">
              {attachment.mime_type === 'application/pdf' && (
                <button
                  onClick={() => setPreviewDocumentId(attachment.document_id)}
                  className="px-3 py-1.5 text-sm font-medium text-blue-600 bg-blue-50 rounded-md hover:bg-blue-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1"
                >
                  Preview
                </button>
              )}
              <a
                href={attachment.download_url}
                download={attachment.file_name}
                className="px-3 py-1.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1"
              >
                Download
              </a>
            </div>
          </div>
        </div>
      ))}

      {/* Preview Modal */}
      {previewDocumentId && (
        <AttachmentPreview
          documentId={previewDocumentId}
          onClose={() => setPreviewDocumentId(null)}
        />
      )}
    </div>
  );
}
