# Implementation Plan: Draft Orders UI (Detail View & Editor)

**Branch**: `014-draft-orders-ui` | **Date**: 2025-12-27 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/014-draft-orders-ui/spec.md`

## Summary

Draft Orders UI provides a two-pane detail view for order review and editing. The left pane displays source documents (PDF/Excel) with zoom and navigation controls, while the right pane shows an editable order form with header fields and lines table. The UI handles issue badges, SKU matching dropdowns with candidate suggestions, customer detection panels for ambiguous cases, and keyboard navigation for power users. Action buttons (Retry with AI, Re-run Matching, Approve, Push to ERP) are enabled/disabled based on draft status and permissions, guiding Ops through the workflow. Optimistic updates and virtualization ensure smooth performance for large orders (200+ lines).

**Technical Approach**: Next.js/React frontend with TanStack Query for data fetching/caching, AG-Grid or TanStack Table for virtualized lines table, PDF.js for document rendering, Radix UI for accessible components. Real-time issue feedback via validation API integration. Keyboard shortcuts for power user productivity.

## Technical Context

**Language/Version**: TypeScript + Next.js (React 18+)
**Primary Dependencies**: TanStack Query, TanStack Table/AG-Grid, PDF.js, Radix UI, Tailwind CSS
**Storage**: N/A (frontend, consumes REST APIs)
**Testing**: Jest + React Testing Library (unit/component), Playwright (E2E)
**Target Platform**: Web browsers (Chrome, Firefox, Safari, Edge latest versions)
**Project Type**: web (frontend module within Next.js application)
**Performance Goals**: PDF render <1s p95, table scroll 60fps, issue updates <500ms
**Constraints**: Virtualization required for >50 lines, unsaved changes warning mandatory
**Scale/Scope**: Support 200-line drafts, 100 concurrent users, <2min review time for 50-line draft

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Compliance | Notes |
|-----------|------------|-------|
| **I. SSOT-First** | ✅ Pass | All API contracts defined in SSOT §8.6, UI behavior per §9.4 |
| **II. Hexagonal Architecture** | ✅ Pass | Frontend adapters for API clients (Draft API, Product Search, Validation API), UI layer independent of API implementation |
| **III. Multi-Tenant Isolation** | ✅ Pass | org_id passed via authenticated API calls, never trusted from client |
| **IV. Idempotent Processing** | ✅ Pass | Optimistic updates with rollback on error, save operations idempotent via API |
| **V. AI-Layer Deterministic Control** | ✅ Pass | AI controls via backend API ("Retry with AI" button), budget gates enforced server-side |
| **VI. Observability First-Class** | ✅ Pass | Client-side error tracking (Sentry-compatible), API request correlation via request_id |
| **VII. Test Pyramid Discipline** | ✅ Pass | Unit (component rendering, keyboard handlers), Integration (full workflow), E2E (Playwright), Performance (200-line draft) |

## Project Structure

### Documentation (this feature)

```text
specs/014-draft-orders-ui/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (TypeScript types)
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── openapi.yaml     # API contract reference
└── spec.md              # Feature specification (already exists)
```

### Source Code (repository root)

```text
frontend/
├── src/
│   ├── components/
│   │   ├── drafts/
│   │   │   ├── DraftDetailView.tsx        # Main two-pane layout
│   │   │   ├── DocumentViewer.tsx         # Left pane: PDF/Excel viewer
│   │   │   ├── DraftEditor.tsx            # Right pane: Header + Lines + Actions
│   │   │   ├── HeaderForm.tsx             # Customer, dates, currency fields
│   │   │   ├── CustomerDetectionPanel.tsx # Ambiguous customer selection
│   │   │   ├── LinesTable.tsx             # Virtualized lines table
│   │   │   ├── LineRow.tsx                # Editable line row
│   │   │   ├── InternalSkuDropdown.tsx    # SKU dropdown with candidates
│   │   │   ├── IssueBadge.tsx             # Issue severity badges
│   │   │   ├── IssuePanel.tsx             # Side panel for issue details
│   │   │   ├── ActionBar.tsx              # Top action buttons
│   │   │   └── __tests__/                 # Component unit tests
│   │   └── ui/                            # Reusable Radix UI components
│   ├── pages/
│   │   └── drafts/
│   │       └── [id].tsx                   # Draft detail page route
│   ├── hooks/
│   │   ├── useDraftDetail.ts              # TanStack Query hook for draft data
│   │   ├── useUpdateLine.ts               # Mutation hook with optimistic updates
│   │   ├── useTableKeyboard.ts            # Keyboard navigation hook
│   │   └── useUnsavedChanges.ts           # Unsaved changes warning hook
│   ├── services/
│   │   ├── api/
│   │   │   ├── drafts.ts                  # Draft API client
│   │   │   ├── products.ts                # Product search API client
│   │   │   └── validations.ts             # Validation API client
│   │   └── types/
│   │       ├── draft.ts                   # TypeScript types from backend
│   │       ├── issue.ts                   # Issue types
│   │       └── matchCandidate.ts          # Match candidate types
│   └── lib/
│       └── utils/
│           ├── keyboardShortcuts.ts       # Keyboard handler utilities
│           └── optimisticUpdates.ts       # Optimistic update helpers
└── tests/
    ├── e2e/
    │   ├── draft-detail.spec.ts           # Playwright E2E tests
    │   └── fixtures/
    └── integration/
        └── draft-workflow.test.ts         # Integration test: open → edit → save
```

**Structure Decision**: Frontend follows Next.js web application structure with modular component organization. Drafts feature is isolated in `components/drafts/` with dedicated API clients, hooks, and types. Virtualization via TanStack Table enables performance for large orders. Radix UI provides accessible, composable primitives.

## Complexity Tracking

> **No violations to justify**
