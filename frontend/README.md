# OrderFlow Frontend

Next.js 14 frontend for the OrderFlow B2B order automation platform.

## Tech Stack

- **Framework:** Next.js 14 (App Router)
- **Language:** TypeScript
- **Styling:** Tailwind CSS
- **Components:** shadcn/ui (Radix UI primitives)
- **Data Fetching:** TanStack Query (React Query)
- **HTTP Client:** Axios
- **PDF Viewer:** react-pdf

## Getting Started

### Prerequisites

- Node.js 18+ and npm/yarn/pnpm

### Installation

```bash
# Install dependencies
npm install

# Copy environment variables
cp .env.example .env

# Start development server
npm run dev
```

The app will be available at [http://localhost:3000](http://localhost:3000).

### Environment Variables

- `NEXT_PUBLIC_API_URL` - Backend API URL (default: http://localhost:8000)

## Project Structure

```
frontend/
├── src/
│   ├── app/              # Next.js app router pages
│   │   ├── layout.tsx    # Root layout with providers
│   │   ├── page.tsx      # Home page (redirects to /inbox)
│   │   ├── globals.css   # Global styles & Tailwind
│   │   └── providers.tsx # TanStack Query provider
│   ├── components/
│   │   └── ui/           # shadcn/ui components
│   └── lib/
│       ├── api.ts        # Axios instance with interceptors
│       ├── types.ts      # Shared TypeScript types
│       └── utils.ts      # Utility functions
├── package.json
├── tsconfig.json
├── tailwind.config.ts
└── next.config.js
```

## Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm start` - Start production server
- `npm run lint` - Run ESLint
- `npm run type-check` - Run TypeScript compiler check

## Type Definitions

All domain types are defined in `src/lib/types.ts` and mirror the backend Pydantic models:

- `InboundMessage` - Email/upload intake
- `Document` - File attachments
- `DraftOrder` - Extracted order headers
- `DraftOrderLine` - Order line items
- `Product`, `Customer` - Catalog entities
- `ValidationIssue` - Validation errors/warnings
- `SKUMapping` - Customer SKU mappings

## API Client

The `api` instance in `src/lib/api.ts`:

- Configured base URL from environment
- Includes credentials for auth cookies
- Request interceptor for auth headers
- Response interceptor for error handling (401 redirects to /login)

## Multi-Tenant Considerations

All API calls must include proper `org_id` filtering. The backend enforces multi-tenant isolation and returns 404 (not 403) for cross-tenant access attempts.

## Development Guidelines

1. Follow Next.js App Router conventions (Server Components by default)
2. Use TanStack Query for all data fetching
3. Prefer shadcn/ui components over custom implementations
4. Keep types in sync with backend models (reference SSOT_SPEC.md)
5. Use the `cn()` utility for conditional Tailwind classes

## License

Proprietary - OrderFlow Platform
