# Quickstart: Draft Orders UI

**Feature**: 014-draft-orders-ui
**Date**: 2025-12-27

## Prerequisites

- Node.js 20+ and npm/yarn installed
- Backend API running (see 013-draft-orders-core)
- PostgreSQL database with draft orders seeded (optional for dev)

## Development Setup

### 1. Install Dependencies

```bash
cd frontend
npm install
# or
yarn install
```

### 2. Environment Configuration

Create `.env.local`:

```bash
# API Endpoints
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws # Optional: real-time updates

# Feature Flags
NEXT_PUBLIC_ENABLE_PDF_VIEWER=true
NEXT_PUBLIC_ENABLE_EXCEL_VIEWER=true
NEXT_PUBLIC_ENABLE_KEYBOARD_SHORTCUTS=true

# Sentry (optional)
NEXT_PUBLIC_SENTRY_DSN=https://your-sentry-dsn
NEXT_PUBLIC_SENTRY_ENVIRONMENT=development
```

### 3. Run Development Server

```bash
npm run dev
# or
yarn dev
```

Frontend available at: `http://localhost:3000`

### 4. Navigate to Draft Detail View

```
http://localhost:3000/drafts/{draft-id}
```

Example (if seeded): `http://localhost:3000/drafts/00000000-0000-0000-0000-000000000001`

## Testing

### Unit Tests

```bash
# Run all tests
npm run test

# Run tests in watch mode
npm run test:watch

# Run tests with coverage
npm run test:coverage
```

### E2E Tests

```bash
# Install Playwright (first time only)
npx playwright install

# Run E2E tests
npm run test:e2e

# Run E2E tests in UI mode (interactive)
npm run test:e2e:ui
```

### Component Storybook (optional)

```bash
npm run storybook
```

Storybook available at: `http://localhost:6006`

## Key Files to Edit

### Components

- `src/components/drafts/DraftDetailView.tsx` - Main entry point
- `src/components/drafts/LinesTable.tsx` - Lines table logic
- `src/components/drafts/InternalSkuDropdown.tsx` - Match candidate dropdown

### API Clients

- `src/services/api/drafts.ts` - Draft API client
- `src/services/api/products.ts` - Product search API client

### Hooks

- `src/hooks/useDraftDetail.ts` - Data fetching hook
- `src/hooks/useUpdateLine.ts` - Line update mutation

## Common Tasks

### Add New Issue Type

1. Update `IssueType` enum in `src/services/types/issue.ts`
2. Add color mapping in `src/components/drafts/IssueBadge.tsx`
3. Add resolution logic in `src/components/drafts/IssuePanel.tsx`

### Add New Action Button

1. Add button in `src/components/drafts/ActionBar.tsx`
2. Add API method in `src/services/api/drafts.ts`
3. Add mutation hook in `src/hooks/useDraftActions.ts`
4. Update enablement logic based on draft status

### Customize Keyboard Shortcuts

Edit `src/hooks/useTableKeyboard.ts`:

```typescript
const handleKeyDown = (e: KeyboardEvent) => {
  if (e.key === 'n' && e.ctrlKey) {
    e.preventDefault();
    onAddLine(); // Custom shortcut: Ctrl+N for new line
  }
  // ... existing shortcuts
};
```

## Debugging

### TanStack Query DevTools

Automatically enabled in development. Open React DevTools and click "TanStack Query" tab to inspect cache state, mutations, and query status.

### Redux DevTools (if using Redux)

Not applicable - using TanStack Query for state management.

### React DevTools Profiler

Use to identify performance bottlenecks:

1. Open React DevTools
2. Click "Profiler" tab
3. Click record, interact with lines table, stop recording
4. Analyze component render times

### PDF.js Console Logs

Enable PDF.js debugging in browser console:

```javascript
window.PDFJS_VERBOSITY_LEVEL = 5; // 0=errors only, 5=all logs
```

## Performance Tips

### Virtualization Testing

Test with large datasets:

```bash
# Generate 200-line draft for testing
npm run seed:large-draft
```

Expected performance:
- Initial render: <1s
- Scroll: 60fps
- Line edit save: <200ms

### PDF Rendering Optimization

For slow PDF rendering:
1. Reduce `scale` prop in `DocumentViewer` (default: 1.5)
2. Enable text layer caching (enabled by default)
3. Lazy load pages (only render visible + buffer)

### Bundle Size Analysis

```bash
npm run build
npm run analyze
```

Opens bundle analyzer to identify large dependencies.

## Troubleshooting

### Issue: PDF not rendering

**Symptoms**: Blank PDF viewer or "Failed to load PDF" error

**Solutions**:
1. Check CORS headers on API (must allow PDF preview URLs)
2. Verify signed URL not expired (default: 1 hour)
3. Check browser console for PDF.js errors
4. Try different PDF (some PDFs are corrupt/unsupported)

### Issue: Lines table not scrolling smoothly

**Symptoms**: Choppy scroll, low FPS

**Solutions**:
1. Verify virtualization enabled (`estimateSize` prop set)
2. Check for heavy render in `LineRow` component (use React.memo)
3. Reduce concurrent re-renders (debounce search inputs)
4. Profile with React DevTools to find bottleneck

### Issue: Unsaved changes warning not working

**Symptoms**: Can navigate away with unsaved changes

**Solutions**:
1. Verify `beforeunload` event listener attached
2. Check `isDirty` state in `useUnsavedChanges` hook
3. Ensure mutation queue tracked correctly
4. Test in production build (some warnings disabled in dev)

### Issue: Dropdown not showing candidates

**Symptoms**: Empty dropdown when clicking internal_sku

**Solutions**:
1. Check `match_debug_json` not null in API response
2. Verify product search API responding (check Network tab)
3. Check search debounce not too aggressive (default: 300ms)
4. Inspect TanStack Query cache for product search query

### Issue: Action buttons always disabled

**Symptoms**: "Approve" button greyed out even when ready

**Solutions**:
1. Check draft.status is "READY" (inspect API response)
2. Verify user role is OPS or ADMIN (check auth token)
3. Check blocking issues count (must be 0 for approval)
4. Inspect button enablement logic in `ActionBar.tsx`

## Best Practices

### 1. Always Use Hooks for Data Fetching

❌ Don't fetch in component:
```tsx
useEffect(() => {
  fetch('/api/drafts/123').then(r => r.json()).then(setDraft);
}, []);
```

✅ Use custom hook:
```tsx
const { data: draft } = useDraftDetail(draftId);
```

### 2. Debounce Search Inputs

❌ Search on every keystroke:
```tsx
<input onChange={(e) => searchProducts(e.target.value)} />
```

✅ Debounce 300ms:
```tsx
const debouncedSearch = useDebouncedValue(search, 300);
useQuery(['products', debouncedSearch], () => searchProducts(debouncedSearch));
```

### 3. Use Optimistic Updates for Mutations

❌ Wait for server response:
```tsx
await updateLine(lineId, updates);
// UI frozen during request
```

✅ Optimistic update with rollback:
```tsx
const mutation = useMutation({
  mutationFn: updateLine,
  onMutate: (updates) => optimisticallyUpdateCache(updates),
  onError: (err, updates, context) => rollbackCache(context),
});
```

### 4. Memoize Expensive Computations

❌ Recalculate on every render:
```tsx
const filteredCandidates = candidates.filter(c => c.confidence > 0.5);
```

✅ Memoize:
```tsx
const filteredCandidates = useMemo(
  () => candidates.filter(c => c.confidence > 0.5),
  [candidates]
);
```

## Next Steps

1. **Implement Customer Detection Panel** (FR-006)
2. **Add Keyboard Shortcuts** (FR-019)
3. **Integrate with Real-Time Validation API** (FR-013)
4. **Add E2E Tests** for happy path workflow
5. **Optimize Bundle Size** (code splitting, tree shaking)

## Resources

- [Next.js Docs](https://nextjs.org/docs)
- [TanStack Query Docs](https://tanstack.com/query/latest/docs/react/overview)
- [Radix UI Primitives](https://www.radix-ui.com/primitives/docs/overview/introduction)
- [React Testing Library](https://testing-library.com/docs/react-testing-library/intro/)
- [Playwright Docs](https://playwright.dev/docs/intro)
