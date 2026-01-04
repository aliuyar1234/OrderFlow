# Data Model: Inbox UI

**Feature**: 008-inbox-ui | **Date**: 2025-12-27

## TypeScript Types

### InboxItem

```typescript
export interface InboxItem {
  id: string;  // UUID
  source: 'EMAIL' | 'UPLOAD';
  from_email?: string;
  to_email?: string;
  subject?: string;
  received_at: string;  // ISO timestamp
  status: InboundMessageStatus;
  attachment_count: number;
  draft_order_ids: string[];  // UUIDs
  created_at: string;
}

export type InboundMessageStatus =
  | 'RECEIVED'
  | 'STORED'
  | 'PARSED'
  | 'FAILED';
```

### InboxFilters

```typescript
export interface InboxFilters {
  status?: InboundMessageStatus;
  from_email?: string;
  date_from?: string;  // ISO date
  date_to?: string;    // ISO date
  q?: string;          // Search query
}
```

### MessageDetail

```typescript
export interface MessageDetail {
  id: string;
  source: 'EMAIL' | 'UPLOAD';
  from_email?: string;
  to_email?: string;
  subject?: string;
  received_at: string;
  status: InboundMessageStatus;
  source_message_id?: string;
  attachments: Attachment[];
  draft_orders: DraftOrderSummary[];
  created_at: string;
}

export interface Attachment {
  document_id: string;
  file_name: string;
  mime_type: string;
  size_bytes: number;
  status: DocumentStatus;
  page_count?: number;
  preview_url?: string;
  download_url: string;
}

export interface DraftOrderSummary {
  id: string;
  status: string;
  customer_name?: string;
  line_count: number;
  created_at: string;
}
```

### Pagination

```typescript
export interface InboxListResponse {
  items: InboxItem[];
  next_cursor?: string;
}
```

## API Client Types

```typescript
// services/api/inbox.ts
export const inboxApi = {
  async fetchInbox(
    filters: InboxFilters,
    cursor?: string
  ): Promise<InboxListResponse> {
    const params = new URLSearchParams({
      ...filters,
      ...(cursor && { cursor })
    });

    const response = await fetch(`/api/v1/inbox?${params}`);
    return response.json();
  },

  async fetchMessage(id: string): Promise<MessageDetail> {
    const response = await fetch(`/api/v1/inbox/${id}`);
    return response.json();
  }
};
```

## React Component Props

```typescript
// InboxTable.tsx
export interface InboxTableProps {
  filters: InboxFilters;
  onFilterChange: (filters: InboxFilters) => void;
}

// AttachmentPreview.tsx
export interface AttachmentPreviewProps {
  documentId: string;
  fileName: string;
  onClose: () => void;
}

// StatusBadge.tsx
export interface StatusBadgeProps {
  status: InboundMessageStatus;
}
```
