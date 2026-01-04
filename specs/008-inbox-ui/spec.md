# Feature Specification: Inbox UI

**Feature Branch**: `008-inbox-ui`
**Created**: 2025-12-27
**Status**: Draft
**Module**: inbox, documents
**SSOT References**: §8.5 (Inbox API), §9.2 (Inbox UI)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View Inbox List (Priority: P1)

As an OPS user, I need to see a list of all incoming messages (emails and uploads) so that I can triage and process new orders.

**Why this priority**: The inbox is the primary entry point for order processing. Without it, users cannot discover new orders to process.

**Independent Test**: Can be fully tested by creating test inbound messages via API, loading the inbox page, and verifying all messages appear in the list with correct metadata. Delivers core inbox visibility.

**Acceptance Scenarios**:

1. **Given** there are inbound messages in the system, **When** I navigate to the inbox, **Then** I see a list of messages sorted by received_at (newest first)
2. **Given** an inbound message has attachments, **When** I view the inbox list, **Then** I see the attachment count for that message
3. **Given** an inbound message has been processed into a draft order, **When** I view the inbox list, **Then** I see a link/badge indicating a draft exists
4. **Given** I am logged in as Org A, **When** I view the inbox, **Then** I only see messages for Org A (multi-tenant isolation)

---

### User Story 2 - Filter and Search Inbox (Priority: P2)

As an OPS user, I need to filter the inbox by status, date, and sender so that I can quickly find specific messages or focus on unprocessed items.

**Why this priority**: As the inbox grows, finding specific messages becomes difficult. Filtering improves efficiency and reduces triage time.

**Independent Test**: Can be tested by creating messages with different statuses and senders, applying various filters, and verifying the list shows only matching messages.

**Acceptance Scenarios**:

1. **Given** I apply a status filter for "PARSED", **When** the inbox refreshes, **Then** I only see messages with status=PARSED
2. **Given** I enter a sender email in the search field, **When** I submit the search, **Then** I only see messages from that sender
3. **Given** I filter by date range, **When** the inbox refreshes, **Then** I only see messages received within that range
4. **Given** I clear all filters, **When** the inbox refreshes, **Then** I see all messages again

---

### User Story 3 - View Message Details (Priority: P1)

As an OPS user, I need to view full details of an inbound message including all attachments so that I can understand what was received and take appropriate action.

**Why this priority**: List view shows summaries only. Detail view is essential for understanding message content and accessing documents.

**Independent Test**: Can be tested by clicking on a message in the inbox list, verifying the detail view shows all metadata (from, to, subject, date) and lists all attachments with download links.

**Acceptance Scenarios**:

1. **Given** I click on a message in the inbox, **When** the detail view loads, **Then** I see full message metadata (From, To, Subject, Received At, Message-ID)
2. **Given** a message has attachments, **When** I view the detail, **Then** I see a list of all attachments with file names, sizes, and types
3. **Given** an attachment has been processed, **When** I view the detail, **Then** I see the processing status (e.g., "Extraction complete", "Draft created")
4. **Given** a message has a linked draft order, **When** I view the detail, **Then** I see a link to view the draft order

---

### User Story 4 - View and Download Attachments (Priority: P1)

As an OPS user, I need to view and download document attachments so that I can inspect the original files and verify extraction accuracy.

**Why this priority**: Viewing original documents is essential for verifying extraction correctness and handling edge cases.

**Independent Test**: Can be tested by clicking on an attachment in the detail view, verifying it downloads with the correct filename and content matches the original upload.

**Acceptance Scenarios**:

1. **Given** an attachment exists, **When** I click the download button, **Then** the file downloads with the original filename
2. **Given** a PDF attachment exists, **When** I click the preview button, **Then** I see an inline PDF viewer displaying the document
3. **Given** an Excel attachment exists, **When** I click the download button, **Then** the file downloads and opens correctly in Excel
4. **Given** an attachment has a preview image, **When** I view the detail, **Then** I see a thumbnail/preview of the first page

---

### User Story 5 - Navigate to Draft Orders (Priority: P1)

As an OPS user, I need to navigate from an inbox message to its associated draft order(s) so that I can continue processing the order.

**Why this priority**: The inbox is just the entry point. Users need quick navigation to the draft order to approve and push it.

**Independent Test**: Can be tested by creating an inbox message with a linked draft order, clicking the "View Draft" link, and verifying it navigates to the correct draft detail page.

**Acceptance Scenarios**:

1. **Given** an inbox message has a linked draft order, **When** I click "View Draft" in the inbox detail, **Then** I navigate to the draft order detail page
2. **Given** an inbox message has multiple documents that created multiple drafts, **When** I view the inbox detail, **Then** I see links to all associated drafts
3. **Given** an inbox message has no draft yet (still processing), **When** I view the detail, **Then** I see "Processing..." status instead of a draft link
4. **Given** extraction failed, **When** I view the inbox detail, **Then** I see an error message and option to retry

---

### Edge Cases

- What happens when the inbox has 1000+ messages (pagination)?
- How does the UI handle very long email subjects or sender names (text truncation)?
- What happens when an attachment is missing from object storage (DB record exists but file missing)?
- How does the UI indicate processing status for recently uploaded files (real-time updates)?
- What happens when a draft order is deleted after being created from an inbox message (orphaned link)?
- How does the UI handle attachments with very long filenames?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: UI MUST display paginated list of inbound messages (default 50 per page)
- **FR-002**: UI MUST show message metadata in list: Received At, From, Subject, Attachment Count, Status, Draft Link
- **FR-003**: UI MUST provide filters for: Status, Sender Email, Date Range
- **FR-004**: UI MUST provide search functionality on subject and sender
- **FR-005**: UI MUST show message detail view with full metadata and attachment list
- **FR-006**: UI MUST provide download links for each attachment
- **FR-007**: UI MUST provide inline PDF preview for PDF attachments (optional but recommended)
- **FR-008**: UI MUST show links to associated draft orders
- **FR-009**: UI MUST indicate processing status (e.g., "Extracting...", "Extraction complete", "Failed")
- **FR-010**: UI MUST respect user role permissions (all authenticated users can view inbox)
- **FR-011**: UI MUST enforce org_id isolation (only show messages for user's org)
- **FR-012**: UI MUST sort messages by received_at DESC by default (newest first)
- **FR-013**: If attachment file is missing from storage, display error 'File unavailable' with retry option and support contact.
- **FR-014**: If linked draft is deleted, show informational message 'Draft was deleted' with option to recreate from document.

### Key Entities (UI Perspective)

- **InboxItem**: UI representation of an inbound_message with aggregated data (attachment count, draft count, processing status). Displayed in the inbox list.

- **MessageDetail**: Full details of an inbound_message including all attachments with their processing status and links to draft orders.

### Technical Constraints

- **TC-001**: UI MUST use Next.js (React) with TypeScript
- **TC-002**: UI MUST use TanStack Query for data fetching and caching
- **TC-003**: UI MUST implement cursor-based pagination (not offset-based)
- **TC-004**: UI MUST handle API errors gracefully with user-friendly messages
- **TC-005**: PDF preview MUST use a client-side library (e.g., react-pdf, pdfjs)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Inbox list loads in under 1 second for 50 messages (P95)
- **SC-002**: Message detail view loads in under 500ms (P95)
- **SC-003**: Filters apply and update list in under 500ms (P95)
- **SC-004**: PDF preview renders in under 2 seconds for typical documents (<10 pages)
- **SC-005**: 100% of attachments are downloadable with correct content
- **SC-006**: Zero cross-org data leaks in UI (verified by multi-tenant tests)

### User Experience

- **UX-001**: Inbox table is responsive and works on tablet devices (min-width: 768px)
- **UX-002**: Long subjects/senders are truncated with tooltips showing full text
- **UX-003**: Processing status updates without requiring page refresh (polling or websocket)
- **UX-004**: Error messages are clear and actionable (e.g., "Extraction failed. Retry?")
- **UX-005**: Navigation between inbox and drafts is intuitive and fast

## Dependencies

- **Depends on**: 002-auth-rbac (authentication, JWT tokens)
- **Depends on**: 003-tenancy-isolation (org_id scoping)
- **Depends on**: 005-object-storage (file downloads)
- **Depends on**: 006-smtp-ingest (inbound messages)
- **Depends on**: 007-document-upload (document records)
- **Dependency reason**: UI consumes APIs from auth, inbox, and documents modules

## Implementation Notes

### Inbox List API (SSOT §8.5)

#### GET `/inbox`

Query parameters:
- `status`: Filter by InboundMessageStatus (e.g., "PARSED")
- `from_email`: Filter by sender email
- `date_from`: ISO date (e.g., "2025-12-01")
- `date_to`: ISO date
- `q`: Search query (subject or sender)
- `limit`: Page size (default 50, max 100)
- `cursor`: Pagination cursor (opaque string)

```json
// Response 200
{
  "items": [
    {
      "id": "uuid",
      "source": "EMAIL",
      "from_email": "buyer@customer.com",
      "to_email": "orders+acme@orderflow.example.com",
      "subject": "PO-12345 Order",
      "received_at": "2025-12-27T10:00:00Z",
      "status": "PARSED",
      "attachment_count": 2,
      "draft_order_ids": ["uuid1"],
      "created_at": "2025-12-27T10:00:01Z"
    }
  ],
  "next_cursor": "base64_encoded_cursor"
}
```

### Message Detail API

#### GET `/inbox/{id}`

```json
// Response 200
{
  "id": "uuid",
  "source": "EMAIL",
  "from_email": "buyer@customer.com",
  "to_email": "orders+acme@orderflow.example.com",
  "subject": "PO-12345 Order",
  "received_at": "2025-12-27T10:00:00Z",
  "status": "PARSED",
  "source_message_id": "<message-id@customer.com>",
  "attachments": [
    {
      "document_id": "uuid",
      "file_name": "order.pdf",
      "mime_type": "application/pdf",
      "size_bytes": 123456,
      "status": "EXTRACTED",
      "page_count": 3,
      "preview_url": "/api/v1/documents/uuid/preview",
      "download_url": "/api/v1/documents/uuid/download"
    }
  ],
  "draft_orders": [
    {
      "id": "uuid",
      "status": "NEEDS_REVIEW",
      "customer_name": "Muster GmbH",
      "line_count": 5,
      "created_at": "2025-12-27T10:01:00Z"
    }
  ],
  "created_at": "2025-12-27T10:00:01Z"
}
```

### Document Download API

#### GET `/documents/{id}/download`

Returns binary file with `Content-Disposition: attachment; filename="order.pdf"`

#### GET `/documents/{id}/preview`

Returns preview image (if available) with `Content-Type: image/jpeg`

#### GET `/documents/{id}`

Returns document metadata (for status checking)

```json
{
  "id": "uuid",
  "file_name": "order.pdf",
  "mime_type": "application/pdf",
  "size_bytes": 123456,
  "status": "EXTRACTED",
  "page_count": 3,
  "error_json": null,
  "created_at": "2025-12-27T10:00:01Z"
}
```

### React Component Structure

```
src/
  app/
    inbox/
      page.tsx              # Inbox list page
      [id]/
        page.tsx            # Message detail page
  components/
    inbox/
      InboxTable.tsx        # Table with filters
      InboxFilters.tsx      # Status, date, sender filters
      MessageDetail.tsx     # Message detail view
      AttachmentList.tsx    # List of attachments
      AttachmentPreview.tsx # PDF preview modal
      DraftOrderLink.tsx    # Link to draft order
```

### InboxTable Component

```tsx
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';

interface InboxFilters {
  status?: string;
  from_email?: string;
  date_from?: string;
  date_to?: string;
  q?: string;
}

export function InboxTable() {
  const [filters, setFilters] = useState<InboxFilters>({});
  const [cursor, setCursor] = useState<string | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ['inbox', filters, cursor],
    queryFn: () => fetchInbox(filters, cursor),
  });

  if (isLoading) return <div>Loading...</div>;
  if (error) return <div>Error loading inbox</div>;

  return (
    <div>
      <InboxFilters filters={filters} onChange={setFilters} />

      <table>
        <thead>
          <tr>
            <th>Received</th>
            <th>From</th>
            <th>Subject</th>
            <th>Attachments</th>
            <th>Status</th>
            <th>Draft</th>
          </tr>
        </thead>
        <tbody>
          {data.items.map((item) => (
            <tr key={item.id} onClick={() => navigate(`/inbox/${item.id}`)}>
              <td>{formatDate(item.received_at)}</td>
              <td>{item.from_email}</td>
              <td>{truncate(item.subject, 50)}</td>
              <td>{item.attachment_count}</td>
              <td><StatusBadge status={item.status} /></td>
              <td>
                {item.draft_order_ids.length > 0 && (
                  <Link to={`/drafts/${item.draft_order_ids[0]}`}>
                    View Draft
                  </Link>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {data.next_cursor && (
        <button onClick={() => setCursor(data.next_cursor)}>
          Load More
        </button>
      )}
    </div>
  );
}
```

### PDF Preview Component

```tsx
import { Document, Page } from 'react-pdf';
import { useState } from 'react';

interface AttachmentPreviewProps {
  documentId: string;
}

export function AttachmentPreview({ documentId }: AttachmentPreviewProps) {
  const [numPages, setNumPages] = useState<number>(0);
  const [pageNumber, setPageNumber] = useState(1);

  const downloadUrl = `/api/v1/documents/${documentId}/download`;

  return (
    <div>
      <Document
        file={downloadUrl}
        onLoadSuccess={({ numPages }) => setNumPages(numPages)}
      >
        <Page pageNumber={pageNumber} />
      </Document>

      {numPages > 1 && (
        <div>
          <button
            disabled={pageNumber <= 1}
            onClick={() => setPageNumber(pageNumber - 1)}
          >
            Previous
          </button>
          <span>Page {pageNumber} of {numPages}</span>
          <button
            disabled={pageNumber >= numPages}
            onClick={() => setPageNumber(pageNumber + 1)}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
```

### Status Badge Component

```tsx
type Status = 'RECEIVED' | 'STORED' | 'PARSED' | 'FAILED';

const STATUS_COLORS: Record<Status, string> = {
  RECEIVED: 'bg-blue-100 text-blue-800',
  STORED: 'bg-yellow-100 text-yellow-800',
  PARSED: 'bg-green-100 text-green-800',
  FAILED: 'bg-red-100 text-red-800',
};

export function StatusBadge({ status }: { status: Status }) {
  return (
    <span className={`px-2 py-1 rounded text-xs font-medium ${STATUS_COLORS[status]}`}>
      {status}
    </span>
  );
}
```

### Real-time Status Updates (Optional)

Use polling for MVP (websockets in future):

```tsx
import { useQuery } from '@tanstack/react-query';

export function useInboxRealtime() {
  return useQuery({
    queryKey: ['inbox'],
    queryFn: fetchInbox,
    refetchInterval: 10000, // Poll every 10 seconds
  });
}
```

### Error Handling

```tsx
import { useQuery } from '@tanstack/react-query';

export function InboxTable() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['inbox'],
    queryFn: fetchInbox,
    retry: 3,
    onError: (error) => {
      toast.error('Failed to load inbox. Please try again.');
    },
  });

  if (error) {
    return (
      <div className="error-state">
        <p>Unable to load inbox</p>
        <button onClick={() => refetch()}>Retry</button>
      </div>
    );
  }

  // ...
}
```

## Out of Scope

- Email reply functionality (read-only inbox)
- Email threading / conversation view
- Bulk actions (select multiple messages)
- Archive / delete messages
- Forward message to another user
- Export inbox to CSV
- Advanced search (full-text search on email body)
- Real-time updates via websocket (polling only for MVP)
- Mobile app (web UI only)
- Drag-and-drop file upload in inbox (upload is separate page)
- Email composition
- Attachment inline editing
- Optical character recognition (OCR) for scanned documents

## Testing Strategy

### Frontend Testing Requirements

Frontend Testing Requirements: Unit/component tests MUST achieve ≥80% coverage. E2E tests MUST cover inbox happy path (list → filter → detail → download attachment). Jest + React Testing Library for unit/component, Playwright for E2E.

### Unit Tests (React Components)
- InboxTable renders with test data
- Filters update correctly
- StatusBadge shows correct colors
- Pagination works (next/prev)
- Text truncation works correctly
- Date formatting is correct

### Integration Tests (API + UI)
- Load inbox list from API
- Apply filters and verify API request
- Click message to navigate to detail
- Download attachment and verify content
- Preview PDF and verify rendering
- Navigate to draft order from inbox
- Multi-tenant isolation (cannot see other org's messages)

### E2E Tests (Browser)
- Login → Navigate to inbox → See messages
- Click message → View detail → Download attachment
- Apply status filter → List updates
- Search by sender → Results match
- Click "View Draft" → Navigate to draft detail
- Upload file → See it appear in inbox (after refresh)

### Performance Tests
- Load inbox with 1000+ messages (paginated)
- Filter inbox with 1000+ messages (<500ms)
- Download 10MB PDF (<5 seconds)
- Render PDF preview (<2 seconds)
- Concurrent users (10+ simultaneous)

### Accessibility Tests
- Keyboard navigation works
- Screen reader announces status correctly
- ARIA labels present on interactive elements
- Color contrast meets WCAG AA standards
- Focus management on navigation

### UI/UX Tests
- Table is responsive (tablet and desktop)
- Long subjects are truncated with tooltips
- Error messages are clear and actionable
- Loading states are visible (spinners)
- Empty state shows helpful message ("No messages yet")
- Attachment icons match file types
