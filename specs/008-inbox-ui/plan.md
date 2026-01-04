# Implementation Plan: Inbox UI

**Branch**: `008-inbox-ui` | **Date**: 2025-12-27 | **Spec**: [spec.md](./spec.md)

## Summary

Implement frontend inbox UI for viewing and triaging inbound messages (emails and uploads). Features paginated list view with filters (status, sender, date), message detail view with attachments, PDF preview, and navigation to draft orders. Built with Next.js (React), TypeScript, TanStack Query for data fetching, and react-pdf for PDF preview.

## Technical Context

**Language/Version**: TypeScript 5.x, React 18
**Primary Dependencies**: Next.js 14, TanStack Query, react-pdf, Tailwind CSS
**Storage**: None (UI layer only)
**Testing**: Vitest, React Testing Library, Playwright (E2E)
**Target Platform**: Modern browsers (Chrome, Firefox, Safari, Edge)
**Project Type**: web
**Performance Goals**: <1s inbox load (50 items), <500ms filter/search response (P95)
**Constraints**: Responsive design (min 768px width), multi-tenant isolation
**Scale/Scope**: Display 1000+ messages with pagination

## Constitution Check

### I. SSOT-First
- **Status**: ✅ PASS
- **Evidence**: Inbox UI specified in SSOT §9.2, API endpoints in §8.5

### II. Hexagonal Architecture
- **Status**: ✅ PASS
- **Evidence**: UI consumes backend API via HTTP. No direct database or storage access.

### III. Multi-Tenant Isolation
- **Status**: ✅ PASS
- **Evidence**: API enforces org_id from JWT. UI displays only user's org data.

### IV. Idempotent Processing
- **Status**: N/A (UI layer)

### V. AI-Layer Deterministic Control
- **Status**: N/A

### VI. Observability First-Class
- **Status**: ✅ PASS
- **Evidence**: TanStack Query provides request/error logging. Performance metrics tracked (page load, API latency).

### VII. Test Pyramid Discipline
- **Status**: ✅ PASS
- **Evidence**: Component tests for React components, integration tests for API interactions, E2E tests for user flows.

## Project Structure

### Documentation (this feature)

```text
specs/008-inbox-ui/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/
    └── api-client-spec.yaml
```

### Source Code (repository root)

```text
frontend/
├── src/
│   ├── app/
│   │   └── inbox/
│   │       ├── page.tsx              # Inbox list page
│   │       └── [id]/
│   │           └── page.tsx          # Message detail page
│   ├── components/
│   │   └── inbox/
│   │       ├── InboxTable.tsx        # Paginated table
│   │       ├── InboxFilters.tsx      # Status/date/sender filters
│   │       ├── MessageDetail.tsx     # Full message view
│   │       ├── AttachmentList.tsx    # Attachment grid
│   │       ├── AttachmentPreview.tsx # PDF preview modal
│   │       └── StatusBadge.tsx       # Status indicator
│   ├── services/
│   │   └── api/
│   │       ├── inbox.ts              # Inbox API client
│   │       └── documents.ts          # Document download API
│   └── types/
│       └── inbox.ts                  # TypeScript types
└── tests/
    ├── components/
    │   └── inbox/
    │       ├── InboxTable.test.tsx
    │       └── StatusBadge.test.tsx
    ├── integration/
    │   └── inbox/
    │       └── inbox-api.test.ts
    └── e2e/
        └── inbox/
            └── inbox-flow.spec.ts
```

**Structure Decision**: Next.js app with dedicated inbox section. Components organized by feature. API services separated from UI components for testability.

## Complexity Tracking

> **No violations identified. All constitution checks pass.**
