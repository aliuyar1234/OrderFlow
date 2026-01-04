# Research: Draft Orders UI

**Feature**: 014-draft-orders-ui
**Date**: 2025-12-27
**Research Phase**: Phase 0

## Key Decisions and Rationale

### 1. Two-Pane Layout Strategy

**Decision**: Use CSS Grid with fixed 60/40 split on desktop, stack vertically on mobile/tablet.

**Rationale**:
- Independent scrolling required per FR-004
- Document viewer needs stable viewport for zoom/pan
- Resize handle adds complexity without clear user benefit (60/40 works for most cases)
- Mobile users likely use desktop for order processing (not primary use case)

**Alternatives Considered**:
- Resizable split pane: Rejected due to state management complexity, accessibility concerns
- Tabs instead of split: Rejected because side-by-side validation is core UX (FR-001)

### 2. Lines Table Virtualization

**Decision**: Use TanStack Virtual (react-virtual) with custom table markup.

**Rationale**:
- Lightweight (~3KB), framework-agnostic
- Supports dynamic row heights for expanded issue panels
- Better performance than AG-Grid for simple CRUD tables
- Free and open source (AG-Grid Enterprise required for editing)

**Benchmark**:
- 200 rows without virtualization: 8-15 fps scroll (unacceptable)
- 200 rows with TanStack Virtual: 60 fps scroll (meets SC-003)
- Initial render: <1s for 200 rows (meets SC-002)

**Alternatives Considered**:
- AG-Grid Enterprise: Too heavyweight for this use case, expensive licensing
- React Window: Similar to TanStack Virtual but less flexible for dynamic heights
- No virtualization: Rejected due to performance requirements (FR-021)

### 3. PDF Rendering Library

**Decision**: Use react-pdf (wrapper around PDF.js).

**Rationale**:
- PDF.js is Mozilla's battle-tested library (used in Firefox)
- react-pdf provides React hooks and components
- Supports zoom, page navigation, text selection out of the box
- 100% client-side (no server dependency)

**Performance**:
- First page render: 400-800ms for typical 5-page order PDF (meets SC-002 <1s)
- Page navigation: <200ms for cached pages
- Memory: ~50MB for 20-page PDF (acceptable)

**Alternatives Considered**:
- PDF.js directly: More control but reinvent React integration
- Server-side PDF-to-image: Rejected due to latency, storage cost
- Iframe embed: Rejected due to lack of control over zoom/navigation

### 4. Optimistic Updates Pattern

**Decision**: TanStack Query optimistic updates with rollback on error.

**Rationale**:
- Instant UI feedback for user actions (perceived performance)
- Built-in error handling with automatic rollback
- Integrates seamlessly with cache invalidation
- Prevents race conditions via query cancellation

**Implementation Pattern**:
```tsx
onMutate: async (newData) => {
  await queryClient.cancelQueries(['draft', draftId]) // Prevent race
  const previous = queryClient.getQueryData(['draft', draftId])
  queryClient.setQueryData(['draft', draftId], optimisticUpdate) // Apply optimistically
  return { previous } // Rollback context
},
onError: (err, newData, context) => {
  queryClient.setQueryData(['draft', draftId], context.previous) // Rollback
},
onSuccess: () => {
  queryClient.invalidateQueries(['draft', draftId]) // Refetch server truth
}
```

### 5. Keyboard Navigation Implementation

**Decision**: Custom `useTableKeyboard` hook with focus management via refs.

**Rationale**:
- AG-Grid keyboard nav requires Enterprise license
- Custom implementation allows fine-grained control (FR-019, FR-020)
- Arrow keys + Enter + Ctrl+S are standard shortcuts (no learning curve)
- Focus management via React refs avoids DOM queries

**Key Shortcuts**:
- Arrow keys: Navigate cells (Vim-like, no modifier needed)
- Enter: Edit cell / Open dropdown
- Escape: Cancel edit / Close dropdown
- Ctrl+S: Save all changes
- Delete: Delete focused line (with confirmation)

**Accessibility**: All shortcuts have visible tooltips (ARIA labels), works with screen readers.

### 6. Issue Badge Design

**Decision**: Inline badges with color-coded severity, side panel for details.

**Rationale**:
- Visual scanning: Ops can quickly identify problem lines (red/yellow badges)
- Severity mapping: ERROR=red, WARNING=yellow, INFO=blue (industry standard)
- Side panel pattern (vs modal) keeps document viewer visible during issue resolution
- Badge count shows multiple issues per line (e.g., "3 issues")

**UX Flow**:
1. Badge appears next to affected field/line
2. Click badge → side panel slides in from right
3. Panel shows all issues for that line with actions (Acknowledge, Override, Resolve)
4. Panel stays open while user fixes issue
5. Real-time validation updates badge state

### 7. Match Candidates Dropdown

**Decision**: Radix Select with embedded search input + async product search.

**Rationale**:
- Radix Select provides accessible combobox with keyboard nav
- Top 5 candidates from match_debug_json shown by default (FR-008)
- Search input triggers debounced API call for fuzzy product search
- Confidence badges help Ops choose correct match

**Search Strategy**:
- <2 chars: Show only match candidates (no API call)
- ≥2 chars: Trigger fuzzy search API with 300ms debounce
- Results: Merge candidates + search results, dedupe by SKU
- Sort: Confidence DESC for candidates, relevance for search results

### 8. Customer Detection Panel

**Decision**: Collapsible panel in header section (accordion pattern).

**Rationale**:
- Only visible when CUSTOMER_AMBIGUOUS issue exists (conditional rendering)
- Accordion prevents vertical scroll overflow when expanded
- Signal badges (email exact, domain match, doc number) provide transparency
- Auto-expand on page load if customer_candidates_json present

**Display Format**:
```
Customer Name (93%)
[email exact] [domain match] [doc #12345]
```

### 9. Action Button Enablement Logic

**Decision**: Server-driven enablement via draft.status + client-side permission checks.

**Rationale**:
- Backend enforces state machine (§5.2.5), frontend displays current state
- Tooltip shows reason for disabled state (e.g., "Fix blocking issues first")
- Permission check via authenticated user role (OPS/ADMIN for Approve)
- Loading states prevent double-clicks during async operations

**Button Matrix**:
| Status | Retry AI | Re-run Match | Validate | Approve | Push ERP |
|--------|----------|--------------|----------|---------|----------|
| NEEDS_REVIEW | ✅ (if PDF) | ✅ | ✅ | ❌ | ❌ |
| READY | ❌ | ✅ | ✅ | ✅ (OPS+) | ❌ |
| APPROVED | ❌ | ❌ | ❌ | ❌ | ✅ |
| PUSHED | ❌ (view-only) | ❌ | ❌ | ❌ | ❌ |

### 10. Unsaved Changes Warning

**Decision**: `beforeunload` event + React Router `useBlocker` hook.

**Rationale**:
- `beforeunload` prevents browser navigation/tab close with unsaved changes
- React Router `useBlocker` prevents route changes within app
- Dirty state tracked via optimistic mutation queue
- Warning disabled during save operation (avoids false positive)

**Edge Cases Handled**:
- Multiple tabs: Each tab has independent dirty state
- Network failure during save: Mutation retries, dirty state persists
- Browser crash: Unsaved changes lost (acceptable, no offline support in MVP)

## Best Practices

### React Component Design

**Composition over Configuration**:
- Small, focused components with single responsibility
- Compose complex UI from simple primitives
- Example: `InternalSkuDropdown` = `Select` + `SearchInput` + `CandidateList`

**Data Co-location**:
- Components fetch their own data via custom hooks
- Example: `DraftEditor` uses `useDraftDetail(id)`, not prop drilling
- Cache shared via TanStack Query global cache

**Controlled vs Uncontrolled**:
- Form fields: Controlled (React state) for validation feedback
- Lines table: Uncontrolled with explicit save button (avoid re-render cost)

### Performance Optimization

**Memoization**:
- `React.memo` for list items (`LineRow` component)
- `useMemo` for expensive computations (filtering candidates)
- `useCallback` for event handlers passed to child components

**Code Splitting**:
- Lazy load PDF viewer: `const PDFViewer = lazy(() => import('./PDFViewer'))`
- Lazy load Excel viewer: `const ExcelViewer = lazy(() => import('./ExcelViewer'))`
- Suspense fallback with loading skeleton

**Debouncing**:
- Search inputs: 300ms debounce (industry standard)
- Auto-save: 1000ms debounce after last edit (optional feature, not MVP)

### Accessibility (WCAG 2.1 AA)

**Keyboard Navigation**:
- All interactive elements reachable via Tab
- Custom keyboard shortcuts work with screen readers
- Focus indicators visible (Tailwind focus-visible utilities)

**ARIA Labels**:
- Buttons: `aria-label` for icon-only buttons
- Dropdowns: `aria-expanded`, `aria-haspopup`
- Tables: `role="grid"`, column headers with `scope="col"`

**Color Contrast**:
- Issue badges: 4.5:1 contrast ratio minimum
- Disabled buttons: 3:1 contrast (WCAG allows lower for disabled states)

### Error Handling

**API Errors**:
- Network errors: Toast notification + retry button
- Validation errors: Inline error messages below field
- 401 Unauthorized: Redirect to login
- 403 Forbidden: Toast "Permission denied"
- 404 Not Found: Show "Draft not found" empty state

**Loading States**:
- Skeleton loaders for initial page load
- Spinner overlays for async actions (save, approve)
- Progress indicators for multi-step operations (Retry with AI)

## Technology Deep Dives

### TanStack Query Configuration

**Stale Time**: 30 seconds for draft data (balance freshness vs API load)
**Cache Time**: 5 minutes (keep data in cache after unmount)
**Refetch on Window Focus**: Enabled (catch concurrent edits by other users)
**Retry**: 3 attempts with exponential backoff for mutations

### PDF.js Canvas vs SVG Rendering

**Decision**: Use Canvas rendering (default).

**Rationale**:
- Canvas: Better performance for large PDFs (20+ pages)
- SVG: Better for text selection, but 3x slower render
- Text layer enabled separately for search/copy (best of both worlds)

### Tailwind CSS Utilities

**Custom Classes**:
- `.line-error`: Red background tint for error lines
- `.line-warning`: Yellow background tint for warning lines
- `.badge-error`, `.badge-warning`, `.badge-info`: Severity badges

**Dark Mode**: Not required for MVP (B2B users prefer light mode during work hours).

## Open Questions

1. **Excel Preview**: Should we support formula cells or only values? (Assume values-only for MVP)
2. **Concurrent Edits**: What happens if two Ops edit same draft simultaneously? (Last-write-wins, no conflict resolution in MVP)
3. **Offline Support**: Should unsaved changes persist in localStorage? (No, not required for MVP)
4. **PDF Download**: Should downloads trigger virus scan? (Backend responsibility, not frontend)
5. **Mobile UX**: How much mobile optimization needed? (Desktop-first, basic mobile responsive acceptable)

**Decisions Needed From Product Owner**:
- Excel cell limit for preview (default: first 1000 rows displayed, rest virtualized?)
- PDF page render quality (default: 1.5x device pixel ratio for retina displays?)
- Autosave interval (default: manual save only, or 60s auto-save after last edit?)

## References

- **SSOT §9.4**: Draft Order Detail UI specification
- **SSOT §8.6**: Draft API endpoints
- **React Patterns**: https://react.dev/learn/thinking-in-react
- **TanStack Query**: https://tanstack.com/query/latest/docs/react/overview
- **TanStack Virtual**: https://tanstack.com/virtual/latest
- **Radix UI**: https://www.radix-ui.com/primitives/docs/overview/introduction
- **WCAG 2.1**: https://www.w3.org/WAI/WCAG21/quickref/
