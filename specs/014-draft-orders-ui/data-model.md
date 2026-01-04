# Data Model: Draft Orders UI

**Feature**: 014-draft-orders-ui
**Date**: 2025-12-27

## TypeScript Type Definitions

### Core Entities (from Backend API)

```typescript
// Draft Order Header
export interface DraftOrder {
  id: string; // UUID
  org_id: string; // UUID
  document_id: string | null; // UUID
  customer_id: string | null; // UUID
  customer_candidates_json: CustomerCandidate[] | null;
  customer_confidence: number | null; // 0..1
  external_order_number: string | null;
  order_date: string | null; // ISO date
  currency: string; // 'EUR' | 'CHF' | 'USD'
  requested_delivery_date: string | null; // ISO date
  notes: string | null;
  status: DraftOrderStatus;
  approved_by_user_id: string | null; // UUID
  approved_at: string | null; // ISO datetime
  created_at: string; // ISO datetime
  updated_at: string; // ISO datetime
  lines: DraftOrderLine[];
  issues: ValidationIssue[];
}

export type DraftOrderStatus =
  | 'NEEDS_REVIEW'
  | 'READY'
  | 'APPROVED'
  | 'PUSHED'
  | 'FAILED'
  | 'REJECTED';

// Draft Order Line
export interface DraftOrderLine {
  id: string; // UUID
  draft_order_id: string; // UUID
  line_no: number;
  customer_sku_raw: string | null;
  customer_sku_norm: string | null; // Normalized for matching
  product_description: string | null;
  qty: number;
  uom: string | null;
  unit_price: number | null;
  currency: string | null;
  internal_sku: string | null; // Matched product SKU
  match_confidence: number | null; // 0..1
  match_method: string | null; // 'exact_mapping' | 'hybrid' | 'trigram' | 'embedding'
  match_status: MatchStatus;
  match_debug_json: MatchCandidate[] | null; // Top 5 candidates
  created_at: string;
  updated_at: string;
}

export type MatchStatus =
  | 'MATCHED' // Confirmed mapping applied
  | 'SUGGESTED' // Auto-applied match (high confidence)
  | 'UNMATCHED' // No match found
  | 'OVERRIDDEN'; // Manual selection by Ops

// Match Candidate (from match_debug_json)
export interface MatchCandidate {
  sku: string;
  name: string;
  confidence: number; // 0..1
  method: 'exact_mapping' | 'hybrid' | 'trigram' | 'embedding';
  features: {
    S_tri?: number; // Trigram similarity
    S_tri_sku?: number; // SKU trigram
    S_tri_desc?: number; // Description trigram
    S_emb?: number; // Embedding similarity
    P_uom?: number; // UoM penalty
    P_price?: number; // Price penalty
  };
}

// Customer Detection Candidate
export interface CustomerCandidate {
  customer_id: string; // UUID
  customer_name: string;
  customer_erp_number: string | null;
  score: number; // 0..1
  signals: {
    email_exact?: boolean;
    email_domain?: boolean;
    doc_number?: boolean;
    name_similarity?: number;
  };
  status: 'SELECTED' | 'REJECTED' | 'PENDING';
}

// Validation Issue
export interface ValidationIssue {
  id: string; // UUID
  draft_order_id: string; // UUID
  line_id: string | null; // UUID (null for header issues)
  issue_type: IssueType;
  severity: IssueSeverity;
  message: string;
  details_json: Record<string, any> | null;
  is_blocking: boolean;
  acknowledged_by_user_id: string | null;
  acknowledged_at: string | null;
  created_at: string;
  updated_at: string;
}

export type IssueType =
  | 'MISSING_CUSTOMER'
  | 'CUSTOMER_AMBIGUOUS'
  | 'UNKNOWN_PRODUCT'
  | 'LOW_CONFIDENCE_MATCH'
  | 'MISSING_PRICE'
  | 'PRICE_MISMATCH'
  | 'UOM_INCOMPATIBLE'
  | 'INVALID_QTY'
  | 'INVALID_DATE';

export type IssueSeverity = 'ERROR' | 'WARNING' | 'INFO';

// Document (for preview)
export interface Document {
  id: string; // UUID
  org_id: string; // UUID
  filename: string;
  content_type: string; // 'application/pdf' | 'application/vnd.ms-excel' | 'text/csv'
  file_size: number; // bytes
  storage_path: string;
  created_at: string;
  preview_url?: string; // Signed URL for viewing
  download_url?: string; // Signed URL for download
}

// Product (for search dropdown)
export interface Product {
  id: string; // UUID
  org_id: string; // UUID
  internal_sku: string;
  name: string;
  description: string | null;
  base_uom: string;
  uom_conversions_json: Record<string, { to_base: number }>;
  active: boolean;
  attributes_json: Record<string, any>;
}
```

### UI-Specific Types

```typescript
// Component Props
export interface DraftDetailViewProps {
  draftId: string;
}

export interface DocumentViewerProps {
  document: Document;
}

export interface DraftEditorProps {
  draft: DraftOrder;
  onSave: (updates: Partial<DraftOrder>) => Promise<void>;
}

export interface LinesTableProps {
  lines: DraftOrderLine[];
  issues: ValidationIssue[];
  onUpdateLine: (lineId: string, updates: Partial<DraftOrderLine>) => Promise<void>;
  onDeleteLine: (lineId: string) => Promise<void>;
  onAddLine: () => Promise<void>;
  onConfirmMapping: (lineId: string, internalSku: string) => Promise<void>;
}

export interface InternalSkuDropdownProps {
  line: DraftOrderLine;
  candidates: MatchCandidate[];
  onSelect: (sku: string | null) => void;
}

export interface IssueBadgeProps {
  issues: ValidationIssue[];
  severity: IssueSeverity;
  onClick: () => void;
}

export interface IssuePanelProps {
  issues: ValidationIssue[];
  onAcknowledge: (issueId: string) => Promise<void>;
  onResolve: (issueId: string) => Promise<void>;
  onClose: () => void;
}

export interface CustomerDetectionPanelProps {
  draft: DraftOrder;
  candidates: CustomerCandidate[];
  onConfirm: (customerId: string) => Promise<void>;
}

export interface ActionBarProps {
  draft: DraftOrder;
  userRole: 'VIEWER' | 'OPS' | 'ADMIN' | 'INTEGRATOR';
  onRetryAI: () => Promise<void>;
  onRerunMatching: () => Promise<void>;
  onRunValidations: () => Promise<void>;
  onApprove: () => Promise<void>;
  onPushERP: () => Promise<void>;
  onReject: () => Promise<void>;
}

// Keyboard Navigation State
export interface TableFocusState {
  lineIndex: number;
  columnKey: string | null; // 'qty' | 'uom' | 'unit_price' | 'internal_sku'
}

// Unsaved Changes Context
export interface UnsavedChangesState {
  isDirty: boolean;
  pendingMutations: number; // Count of in-flight mutations
}

// Form Validation State
export interface FieldError {
  field: string;
  message: string;
}

// PDF Viewer State
export interface PDFViewerState {
  currentPage: number;
  totalPages: number;
  zoom: number; // 0.5 | 1.0 | 1.5 | 2.0 | 'fit-width'
}

// Excel Viewer State
export interface ExcelViewerState {
  currentSheet: number;
  totalSheets: number;
  data: string[][]; // 2D array of cell values
  headers: string[]; // Column headers
}
```

### API Request/Response DTOs

```typescript
// Update Draft Header
export interface UpdateDraftHeaderDTO {
  customer_id?: string | null;
  external_order_number?: string | null;
  order_date?: string | null; // ISO date
  currency?: string;
  requested_delivery_date?: string | null;
  notes?: string | null;
}

// Update Draft Line
export interface UpdateDraftLineDTO {
  customer_sku_raw?: string;
  product_description?: string;
  qty?: number;
  uom?: string;
  unit_price?: number;
  currency?: string;
  internal_sku?: string | null;
}

// Confirm Mapping Request
export interface ConfirmMappingDTO {
  line_id: string;
  internal_sku: string;
}

// Confirm Customer Request
export interface ConfirmCustomerDTO {
  customer_id: string;
}

// Product Search Request
export interface ProductSearchParams {
  search: string;
  limit?: number; // Default: 50
}

// Product Search Response
export interface ProductSearchResult {
  products: Product[];
  total: number;
}

// Approve Draft Request
export interface ApproveDraftDTO {
  // Empty body, approval metadata set server-side
}

// Push to ERP Request
export interface PushToERPDTO {
  // Empty body, push logic server-side
}

// Retry with AI Request
export interface RetryWithAIDTO {
  force_rerun?: boolean; // Default: false
}

// Run Validations Response
export interface ValidationResult {
  issues_count: number;
  blocking_issues_count: number;
  issues: ValidationIssue[];
}
```

### Utility Types

```typescript
// API Response Wrapper
export interface ApiResponse<T> {
  data: T;
  error?: {
    code: string;
    message: string;
    details?: Record<string, any>;
  };
}

// Pagination
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// Issue Grouping (for UI display)
export interface IssuesByLine {
  header: ValidationIssue[];
  lines: Record<string, ValidationIssue[]>; // lineId -> issues
}

// Action Button State
export interface ActionButtonState {
  enabled: boolean;
  loading: boolean;
  tooltip?: string; // Shown when disabled
}
```

## Relationships

```
DraftOrder (1) ──── (many) DraftOrderLine
    │                      │
    │                      │
    └─ (many) ValidationIssue ─ (0..1) ─┘
    │
    └─ (0..1) Document
    │
    └─ (0..1) Customer
    │
    └─ (0..many) CustomerCandidate (via customer_candidates_json)

DraftOrderLine (0..many) ─── (1) Product (via internal_sku)
    │
    └─ (0..many) MatchCandidate (via match_debug_json)
```

## Constraints and Validation

### Client-Side Validation Rules

```typescript
// Draft Header Validation
const validateDraftHeader = (draft: DraftOrder): FieldError[] => {
  const errors: FieldError[] = [];

  if (!draft.customer_id) {
    errors.push({ field: 'customer_id', message: 'Customer is required' });
  }

  if (!draft.order_date) {
    errors.push({ field: 'order_date', message: 'Order date is required' });
  } else if (new Date(draft.order_date) > new Date()) {
    errors.push({ field: 'order_date', message: 'Order date cannot be in the future' });
  }

  if (draft.requested_delivery_date) {
    if (new Date(draft.requested_delivery_date) < new Date(draft.order_date)) {
      errors.push({
        field: 'requested_delivery_date',
        message: 'Delivery date must be after order date',
      });
    }
  }

  return errors;
};

// Draft Line Validation
const validateDraftLine = (line: DraftOrderLine): FieldError[] => {
  const errors: FieldError[] = [];

  if (!line.qty || line.qty <= 0) {
    errors.push({ field: 'qty', message: 'Quantity must be greater than 0' });
  }

  if (line.unit_price !== null && line.unit_price < 0) {
    errors.push({ field: 'unit_price', message: 'Unit price cannot be negative' });
  }

  return errors;
};
```

### Backend Validation (Reference)

- Customer must exist in org (FK constraint)
- Product (internal_sku) must exist and be active (FK constraint)
- UoM must be canonical or in product.uom_conversions_json
- Currency must be in ['EUR', 'CHF', 'USD']
- Status transitions follow state machine (§5.2.5)

## State Management

### TanStack Query Keys

```typescript
// Query Keys
export const draftKeys = {
  all: ['drafts'] as const,
  detail: (id: string) => ['drafts', id] as const,
  lines: (draftId: string) => ['drafts', draftId, 'lines'] as const,
  issues: (draftId: string) => ['drafts', draftId, 'issues'] as const,
};

export const productKeys = {
  all: ['products'] as const,
  search: (query: string) => ['products', 'search', query] as const,
};

export const documentKeys = {
  detail: (id: string) => ['documents', id] as const,
  preview: (id: string) => ['documents', id, 'preview'] as const,
};
```

### Cache Invalidation Rules

```typescript
// After updating draft header
queryClient.invalidateQueries(draftKeys.detail(draftId));

// After updating line
queryClient.invalidateQueries(draftKeys.detail(draftId));
queryClient.invalidateQueries(draftKeys.lines(draftId));

// After running validations
queryClient.invalidateQueries(draftKeys.issues(draftId));
queryClient.invalidateQueries(draftKeys.detail(draftId)); // Status might change

// After approving
queryClient.invalidateQueries(draftKeys.detail(draftId));
queryClient.invalidateQueries(['drafts']); // Refresh list views
```

## Notes

- All IDs are UUIDs (string format in TypeScript, validated server-side)
- All dates are ISO 8601 strings (frontend displays in local timezone)
- All currency amounts are stored as numbers (frontend formats with Intl.NumberFormat)
- Confidence scores are floats 0..1 (frontend displays as percentages)
- JSONB fields (customer_candidates_json, match_debug_json) are parsed to TypeScript types
- Enums are string unions for type safety
