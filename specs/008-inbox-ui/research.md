# Research: Inbox UI

**Feature**: 008-inbox-ui | **Date**: 2025-12-27

## Key Decisions

### 1. TanStack Query for Data Fetching

**Decision**: Use TanStack Query (react-query) for API state management.

**Rationale**:
- Automatic caching and revalidation
- Built-in retry logic
- Optimistic updates support
- Pagination support
- Reduced boilerplate vs. manual fetch

### 2. Cursor-Based Pagination

**Decision**: Use cursor-based pagination (not offset-based).

**Rationale**:
- Stable for real-time data (new emails don't shift pages)
- Better performance for large datasets
- Prevents missed items when data changes

### 3. react-pdf for PDF Preview

**Decision**: Use react-pdf library for inline PDF rendering.

**Rationale**:
- Client-side rendering (no server processing)
- Page navigation support
- Zoom/pan controls
- Widely used, well-maintained

**Alternative Rejected**: iframe with PDF URL (browser-dependent rendering)

### 4. Polling for Status Updates

**Decision**: Poll inbox API every 10 seconds for status updates.

**Rationale**:
- Simple implementation (no WebSocket infrastructure)
- Acceptable for MVP (WebSockets future enhancement)
- TanStack Query handles polling automatically

### 5. Tailwind CSS for Styling

**Decision**: Use Tailwind CSS utility classes for component styling.

**Rationale**:
- Fast development (no custom CSS files)
- Consistent design system
- Responsive utilities built-in
- Easy to maintain

## Best Practices

### TanStack Query Best Practices
- Use query keys for cache invalidation: `['inbox', filters]`
- Enable staleTime for reduced re-fetches
- Handle loading/error states explicitly
- Use prefetch for detail pages

### React Component Best Practices
- Extract reusable components (StatusBadge, AttachmentCard)
- Use TypeScript for props validation
- Handle empty states (no messages)
- Show loading skeletons (not just spinners)

### Performance Best Practices
- Lazy-load PDF preview (only when modal opens)
- Virtualize long lists (react-virtual for 1000+ items)
- Debounce search input (wait 300ms before query)
- Compress images/thumbnails

## Integration Patterns

**Inbox List Flow**:
1. User navigates to /inbox
2. TanStack Query fetches GET /api/v1/inbox
3. Render InboxTable with items
4. User applies filter → Query refetches with params
5. User clicks message → Navigate to /inbox/[id]

**Message Detail Flow**:
1. User clicks message in list
2. Navigate to /inbox/[id]
3. Fetch GET /api/v1/inbox/[id]
4. Render MessageDetail with attachments
5. User clicks attachment → Download or preview
6. User clicks "View Draft" → Navigate to /drafts/[id]
