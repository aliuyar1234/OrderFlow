import { InboxTable } from '@/components/inbox/InboxTable';

export default function InboxPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Inbox</h1>
        <p className="mt-2 text-gray-600">
          View and manage incoming orders from email and uploads
        </p>
      </div>

      <InboxTable />
    </div>
  );
}
