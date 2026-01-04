# Feature Specification: Draft Orders UI (Detail View & Editor)

**Feature Branch**: `014-draft-orders-ui`
**Created**: 2025-12-27
**Status**: Draft
**Module**: draft_orders (frontend)
**SSOT Refs**: §9.4 (Draft Order Detail), §8.6 (Draft API), T-306

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Two-Pane Draft Editor with Document Viewer (Priority: P1)

An Ops user opens a Draft to review extracted data. The left pane shows the source document (PDF/Excel preview), the right pane shows the editable order form with header and lines table, enabling side-by-side validation.

**Why this priority**: Core UX for order review. Ops needs to see source document while editing to catch extraction errors.

**Independent Test**: Open Draft → left pane displays PDF with page navigation → right pane shows header form + lines table → edit line qty → changes save.

**Acceptance Scenarios**:

1. **Given** Draft with PDF document, **When** opening detail view, **Then** left pane renders PDF preview with zoom controls (fit-width, 100%, 150%, 200%) and page navigation
2. **Given** Draft with Excel document, **When** opening detail view, **Then** left pane shows table view of Excel data with column headers
3. **Given** Draft with header data and 10 lines, **When** viewing right pane, **Then** header form shows customer, order_date, currency, delivery_date fields AND lines table shows all 10 lines with columns: line_no, customer_sku_raw, description, qty, uom, unit_price, internal_sku, matching_confidence
4. **Given** Ops scrolls lines table, **When** document viewer is visible, **Then** both panes scroll independently

---

### User Story 2 - Issue Badges and Validation Feedback (Priority: P1)

Validation issues are displayed as badges next to affected lines or header fields. Clicking a badge shows issue details in a side panel. Ops can acknowledge or override issues.

**Why this priority**: Critical for guiding Ops to fix problems before approval. Visual feedback reduces errors.

**Independent Test**: Open Draft with MISSING_PRICE warning → line shows yellow badge → click badge → side panel shows "Unit price not found" → acknowledge → badge updates.

**Acceptance Scenarios**:

1. **Given** line with ERROR severity issue (e.g., UNKNOWN_PRODUCT), **When** rendering line, **Then** red badge appears with issue count, line background tinted red
2. **Given** line with WARNING severity issue (e.g., MISSING_PRICE), **When** rendering line, **Then** yellow badge appears, line background tinted yellow
3. **Given** Ops clicks issue badge, **When** side panel opens, **Then** shows issue type, severity, message, details_json, actions (Acknowledge, Override, Resolve)
4. **Given** Draft has header issue (MISSING_CUSTOMER), **When** viewing header, **Then** customer field shows error badge, field border red
5. **Given** Ops resolves issue (e.g., sets customer), **When** validation re-runs, **Then** badge disappears, field styling resets

---

### User Story 3 - Lines Table with SKU Matching Dropdown (Priority: P1)

Each line shows internal_sku with a dropdown of match candidates (suggestions). Ops can select from candidates or search products. Match confidence is displayed. "Confirm Mapping" button saves mapping as CONFIRMED.

**Why this priority**: Core workflow for correcting/confirming matches. Enables learning loop.

**Independent Test**: Open line with 3 match candidates → dropdown shows candidates sorted by confidence → select candidate #2 → click "Confirm Mapping" → mapping saved.

**Acceptance Scenarios**:

1. **Given** line with match_status=SUGGESTED and 3 candidates, **When** clicking internal_sku dropdown, **Then** shows candidates sorted by matching_confidence DESC with format: "SKU-123 (92%) - Product Name"
2. **Given** Ops selects different candidate from dropdown, **When** saving line, **Then** internal_sku updates, match_status=OVERRIDDEN, match_method="manual", validation re-runs
3. **Given** Ops types in SKU search box, **When** typing "CABLE", **Then** dropdown shows filtered products matching "CABLE" (fuzzy search on internal_sku + name)
4. **Given** Ops selects match candidate and clicks "Confirm Mapping", **When** confirming, **Then** sku_mapping record created with status=CONFIRMED, support_count incremented if exists, feedback_event logged
5. **Given** line with matching_confidence <0.75, **When** rendering, **Then** matching_confidence badge shows yellow warning

---

### User Story 4 - Customer Detection Panel (Priority: P2)

When Draft has ambiguous customer (CUSTOMER_AMBIGUOUS issue), a customer detection panel shows candidate customers with scores and signal badges. Ops selects customer via dropdown and clicks "Confirm Customer".

**Why this priority**: Handles customer ambiguity gracefully. Provides transparency into detection logic.

**Independent Test**: Open Draft with 3 customer candidates → panel shows candidates with scores → select customer #2 → confirm → customer_id set, issue resolved.

**Acceptance Scenarios**:

1. **Given** Draft with customer_candidates_json containing 3 candidates, **When** rendering customer panel, **Then** shows candidates sorted by score DESC with format: "Customer Name (93%)" + signal badges (email match, domain match, doc number)
2. **Given** Ops selects customer from dropdown, **When** clicking "Confirm Customer", **Then** draft.customer_id updated, customer_detection_candidate status=SELECTED, other candidates=REJECTED, CUSTOMER_AMBIGUOUS issue resolved, feedback_event created
3. **Given** customer auto-selected (confidence ≥0.90), **When** rendering panel, **Then** shows "Auto-selected: Customer Name (95%)" with confidence badge, allow manual change
4. **Given** customer manually selected, **When** viewing, **Then** customer_confidence set to max(detection_score, 0.90)

---

### User Story 5 - Action Buttons and Status-Based Enablement (Priority: P1)

Top action bar shows buttons (Retry with AI, Re-run Matching, Run Validations, Approve, Push to ERP) enabled/disabled based on Draft status and permissions.

**Why this priority**: Enforces state machine and guides Ops through workflow steps.

**Independent Test**: Draft in NEEDS_REVIEW → "Approve" disabled, "Retry with AI" enabled → fix issues → status→READY → "Approve" enabled.

**Acceptance Scenarios**:

1. **Given** Draft in NEEDS_REVIEW, **When** rendering actions, **Then** "Retry with AI" enabled (if PDF), "Re-run Matching" enabled, "Approve" disabled (greyed out with tooltip "Fix blocking issues first")
2. **Given** Draft in READY, **When** rendering actions, **Then** "Approve" enabled (green), "Push to ERP" disabled
3. **Given** Draft in APPROVED, **When** rendering actions, **Then** "Push to ERP" enabled, all edit actions disabled
4. **Given** Draft in PUSHED, **When** rendering, **Then** all actions disabled, view-only mode, shows "Pushed to ERP: Order ID XYZ"
5. **Given** Ops clicks "Retry with AI" but budget gate blocks, **When** API returns error, **Then** modal shows "Daily AI budget exceeded. Current usage: €X / €Y. Try again tomorrow or increase budget."
6. **Given** Ops clicks "Approve" on READY draft, **When** approving, **Then** status→APPROVED, approved_by_user_id set, "Approve" button changes to "Push to ERP"

---

### User Story 6 - Keyboard Support for Power Users (Priority: P3)

Ops can navigate lines table with arrow keys, open dropdowns with Enter, save with Ctrl+S, enabling fast keyboard-only editing.

**Why this priority**: Power users process dozens of orders per day. Keyboard shortcuts dramatically improve productivity.

**Independent Test**: Focus line 1 → press Down arrow → focus moves to line 2 → press Enter → SKU dropdown opens → type to search → Enter to select → Ctrl+S to save.

**Acceptance Scenarios**:

1. **Given** focus on line 5 qty field, **When** pressing Down arrow, **Then** focus moves to line 6 qty field
2. **Given** focus on line internal_sku cell, **When** pressing Enter, **Then** dropdown opens, focus on search box
3. **Given** changes made to lines, **When** pressing Ctrl+S, **Then** all changes saved, success toast shown
4. **Given** focus on line, **When** pressing Delete (with confirmation), **Then** line deleted, focus moves to next line

---

### Edge Cases

- What happens when PDF fails to render (large file, corrupt)?
- How does UI handle Drafts with 500+ lines (pagination, virtualization)?
- What happens when user edits Draft while background job is running (race condition)?
- How does system handle slow API responses (loading states, timeouts)?
- What happens when user navigates away with unsaved changes?
- How does UI display Drafts with missing/null document (manual entry)?

## Requirements *(mandatory)*

### Functional Requirements

**Layout & Structure:**
- **FR-001**: UI MUST use two-pane layout (60% document viewer, 40% editor on desktop)
- **FR-002**: UI MUST render PDF documents with:
  - Page navigation (prev/next, page X of Y)
  - Zoom controls (fit-width, 100%, 150%, 200%)
  - Download button
- **FR-003**: UI MUST render Excel/CSV documents as table view with column headers and cell values
- **FR-004**: UI MUST make panes independently scrollable

**Header Form:**
- **FR-005**: UI MUST display header fields:
  - Customer (dropdown with search, shows customer_candidates if ambiguous)
  - External Order Number (editable text)
  - Order Date (date picker, ISO format)
  - Currency (dropdown: EUR, CHF, USD)
  - Requested Delivery Date (date picker, optional)
  - Notes (textarea)
- **FR-006**: UI MUST show customer detection panel when CUSTOMER_AMBIGUOUS issue exists, displaying:
  - Candidates sorted by score DESC
  - Signal badges (email exact, domain match, doc number, name similarity)
  - Dropdown to select + "Confirm Customer" button

**Lines Table:**
- **FR-007**: UI MUST display lines table with columns:
  - line_no (read-only)
  - customer_sku_raw (editable)
  - product_description (editable)
  - qty (editable number, >0 validation)
  - uom (dropdown, canonical UoMs)
  - unit_price (editable number, ≥0)
  - currency (dropdown)
  - internal_sku (dropdown with search + candidates)
  - matching_confidence (read-only badge)
  - issues (badge count, click→details)
  - actions (confirm mapping, delete line)
- **FR-008**: internal_sku dropdown MUST show:
  - Top 5 match candidates sorted by matching_confidence DESC
  - Format: "SKU-123 (92%) - Product Name"
  - Search box for fuzzy product search (internal_sku + name)
  - "No match" option (sets null)
- **FR-009**: UI MUST provide "Add Line" button to insert new line
- **FR-010**: UI MUST allow line deletion with confirmation dialog

**Issue Display:**
- **FR-011**: UI MUST display issue badges:
  - ERROR severity: red badge, red background tint
  - WARNING severity: yellow badge, yellow background tint
  - INFO severity: blue badge
  - Badge shows issue count if multiple
- **FR-012**: UI MUST open side panel when badge clicked, showing:
  - Issue type, severity, message
  - details_json (formatted)
  - Actions: Acknowledge, Override (if allowed), Resolve (auto if condition met)
- **FR-013**: UI MUST update issue badges in real-time after validation re-runs

**Actions:**
- **FR-014**: UI MUST display action buttons in top bar:
  - "Retry with AI" (enabled if status=NEEDS_REVIEW AND document is PDF)
  - "Re-run Matching" (enabled if status ∈ [NEEDS_REVIEW, READY])
  - "Run Validations" (always enabled pre-approval)
  - "Approve" (enabled if status=READY AND user has OPS/ADMIN role)
  - "Push to ERP" (enabled if status=APPROVED)
  - "Reject" (enabled if status ∈ [NEEDS_REVIEW, READY])
- **FR-015**: UI MUST disable buttons based on status and show tooltip explaining why
- **FR-016**: UI MUST show confirmation modal before destructive actions (Reject, Delete Line)
- **FR-017**: UI MUST display loading spinner during async actions (save, approve, push)
- **FR-018**: UI MUST show success/error toasts after actions complete

**Keyboard Support:**
- **FR-019**: UI MUST support keyboard navigation:
  - Arrow keys: navigate cells in lines table
  - Enter: edit cell / open dropdown
  - Escape: close dropdown / cancel edit
  - Ctrl+S: save changes
  - Delete: delete focused line (with confirmation)
- **FR-020**: UI MUST show keyboard shortcut hints (tooltips on hover)

**Performance & Responsiveness:**
- **FR-021**: UI MUST use virtualization for lines table if >50 lines
- **FR-022**: UI MUST debounce search inputs (300ms)
- **FR-023**: UI MUST show loading skeleton while Draft data loads
- **FR-024**: UI MUST warn user before navigating away with unsaved changes
- **FR-025**: PDF render failure handling:
  1. Check file size before rendering - warn if >50MB
  2. Render timeout 30s with fallback message 'PDF preview unavailable'
  3. Corruption detection shows 'PDF may be corrupted - download to view'
  4. Always offer direct download as fallback option

**Tooltip Copy Specification:**
- Approve Button Tooltip Format: When disabled, tooltip displays first 3 blocking reasons from ready_check_json.blocking_reasons. Format: 'Cannot approve: 1) [reason1], 2) [reason2], 3) [reason3]. Fix these issues first.' If >3 reasons, append '...and N more issues'.

### Key Entities

- **Draft Detail View**: React component with left (DocumentViewer) and right (DraftEditor) panes
- **DocumentViewer**: PDF.js or similar for PDF rendering, AG-Grid or similar for Excel/CSV
- **DraftEditor**: Header form + LinesTable + ActionBar
- **LinesTable**: Virtualized table with editable cells and dropdowns
- **IssuePanel**: Slide-out panel for issue details
- **CustomerDetectionPanel**: Collapsible panel in header section

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Ops can review and edit a 50-line Draft in <2 minutes (measured with user testing)
- **SC-002**: PDF viewer renders pages in <1 second on p95
- **SC-003**: Lines table with 200 lines scrolls smoothly (60fps, virtualized)
- **SC-004**: Issue badge updates appear within 500ms after validation completes
- **SC-005**: Keyboard navigation works for ≥90% of common editing tasks (no mouse needed)
- **SC-006**: Action button enablement logic prevents 100% of invalid state transitions
- **SC-007**: Unsaved changes warning prevents accidental data loss in 100% of cases
- **SC-008**: Matching confidence display helps Ops identify low-quality matches (measured by reduced mapping errors)

## Dependencies

- **Depends on**:
  - 013-draft-orders-core (Draft entity, state machine, ready-check)
  - Draft API endpoints (GET /drafts/:id, PATCH /drafts/:id, POST /drafts/:id/lines, etc.)
  - Document viewer API (GET /documents/:id/preview)
  - Product search API (GET /products?search=)
  - Validation API (POST /drafts/:id/validate)
  - Matching API (POST /drafts/:id/match)

- **Blocks**:
  - Ops workflow adoption (UI is primary interface)
  - User acceptance testing

## Technical Notes

### Implementation Guidance

**Tech Stack:**
- Next.js (React) with TypeScript
- TanStack Query (data fetching, caching, optimistic updates)
- AG-Grid or TanStack Table (lines table with virtualization)
- PDF.js or react-pdf (PDF rendering)
- SheetJS or similar (Excel/CSV rendering)
- Radix UI or shadcn/ui (accessible components: dropdowns, modals, tooltips)
- Tailwind CSS (styling)

**Two-Pane Layout:**
```tsx
<div className="flex h-screen">
  <div className="w-3/5 border-r">
    <DocumentViewer documentId={draft.document_id} />
  </div>
  <div className="w-2/5 overflow-y-auto">
    <DraftEditor draft={draft} onSave={handleSave} />
  </div>
</div>
```

**Lines Table with Virtualization:**
```tsx
import { useVirtualizer } from '@tanstack/react-virtual'

function LinesTable({ lines }: { lines: DraftOrderLine[] }) {
  const parentRef = useRef<HTMLDivElement>(null)
  const rowVirtualizer = useVirtualizer({
    count: lines.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 60, // row height
  })

  return (
    <div ref={parentRef} className="h-96 overflow-auto">
      <div style={{ height: `${rowVirtualizer.getTotalSize()}px` }}>
        {rowVirtualizer.getVirtualItems().map((virtualRow) => (
          <LineRow key={virtualRow.index} line={lines[virtualRow.index]} />
        ))}
      </div>
    </div>
  )
}
```

**Optimistic Updates with TanStack Query:**
```tsx
const updateLineMutation = useMutation({
  mutationFn: (data: UpdateLineDTO) => api.updateLine(draftId, lineId, data),
  onMutate: async (newData) => {
    await queryClient.cancelQueries(['draft', draftId])
    const previousDraft = queryClient.getQueryData(['draft', draftId])
    // Optimistically update cache
    queryClient.setQueryData(['draft', draftId], (old) => ({
      ...old,
      lines: old.lines.map(l => l.id === lineId ? { ...l, ...newData } : l)
    }))
    return { previousDraft }
  },
  onError: (err, newData, context) => {
    // Rollback on error
    queryClient.setQueryData(['draft', draftId], context.previousDraft)
  },
  onSuccess: () => {
    // Refetch to get server state
    queryClient.invalidateQueries(['draft', draftId])
  }
})
```

**Match Candidates Dropdown:**
```tsx
function InternalSkuDropdown({ line, candidates }: Props) {
  const [search, setSearch] = useState('')
  const { data: searchResults } = useQuery(
    ['products', 'search', search],
    () => api.searchProducts(search),
    { enabled: search.length >= 2 }
  )

  const items = search ? searchResults : candidates

  return (
    <Select value={line.internal_sku} onValueChange={handleChange}>
      <SelectTrigger>
        {line.internal_sku || 'Select SKU...'}
      </SelectTrigger>
      <SelectContent>
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search products..."
        />
        {items.map((item) => (
          <SelectItem key={item.sku} value={item.sku}>
            {item.sku} ({(item.confidence * 100).toFixed(0)}%) - {item.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
```

**Keyboard Navigation:**
```tsx
function useTableKeyboard(lines: DraftOrderLine[], focusedIndex: number) {
  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setFocusedIndex(Math.min(focusedIndex + 1, lines.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setFocusedIndex(Math.max(focusedIndex - 1, 0))
    } else if (e.key === 's' && e.ctrlKey) {
      e.preventDefault()
      handleSave()
    }
  }

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [focusedIndex])
}
```

### Testing Strategy

**Unit Tests:**
- Component rendering: header form, lines table, issue badges
- Dropdown filtering: match candidates, product search
- Keyboard handlers: arrow keys, Enter, Ctrl+S
- State management: optimistic updates, rollback on error

**Integration Tests:**
- Full workflow: open draft → edit line → save → validate → approve
- Issue resolution: click badge → resolve issue → badge disappears
- Customer selection: choose candidate → confirm → customer_id updated
- Action enablement: verify buttons enabled/disabled per status

**E2E Tests (Playwright/Cypress):**
- Open draft with PDF → verify document renders
- Edit 10 lines using keyboard only → save → verify changes persisted
- Retry with AI → verify loading state → verify result
- Approve → Push to ERP → verify success

**Performance Tests:**
- 200-line Draft: verify table renders in <1s, scrolls at 60fps
- PDF with 20 pages: verify page navigation <1s per page
- 100 concurrent users editing drafts: p95 API latency <500ms

## SSOT References

- **§9.4**: Draft Order Detail UI specification (exact layout, components)
- **§8.6**: Draft API endpoints
- **§5.2.5**: DraftOrderStatus state machine (for action enablement)
- **§6.3**: Ready-check logic (for "Approve" button enablement)
- **§7.8**: Confidence scores (for display in UI)
- **§7.9**: Match confidence (for candidate display)
- **T-306**: Draft Order UI task
