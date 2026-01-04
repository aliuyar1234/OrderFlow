import { cn } from '@/lib/utils';

export type InboxStatus = 'RECEIVED' | 'STORED' | 'PARSED' | 'PROCESSING' | 'FAILED';
export type DraftStatus = 'NEW' | 'EXTRACTED' | 'NEEDS_REVIEW' | 'READY' | 'APPROVED' | 'PUSHING' | 'PUSHED' | 'ERROR';

type Status = InboxStatus | DraftStatus;

const STATUS_STYLES: Record<Status, string> = {
  // Inbox statuses
  RECEIVED: 'bg-blue-100 text-blue-800 border-blue-200',
  STORED: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  PARSED: 'bg-green-100 text-green-800 border-green-200',
  PROCESSING: 'bg-purple-100 text-purple-800 border-purple-200',
  FAILED: 'bg-red-100 text-red-800 border-red-200',

  // Draft statuses
  NEW: 'bg-gray-100 text-gray-800 border-gray-200',
  EXTRACTED: 'bg-blue-100 text-blue-800 border-blue-200',
  NEEDS_REVIEW: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  READY: 'bg-green-100 text-green-800 border-green-200',
  APPROVED: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  PUSHING: 'bg-purple-100 text-purple-800 border-purple-200',
  PUSHED: 'bg-teal-100 text-teal-800 border-teal-200',
  ERROR: 'bg-red-100 text-red-800 border-red-200',
};

interface StatusBadgeProps {
  status: Status;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border',
        STATUS_STYLES[status],
        className
      )}
    >
      {status}
    </span>
  );
}
