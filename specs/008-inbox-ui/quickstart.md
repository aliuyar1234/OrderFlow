# Quickstart: Inbox UI

**Feature**: 008-inbox-ui | **Prerequisites**: Node.js 18+, Backend API running

## Development Setup

### 1. Install Dependencies

```bash
cd frontend
npm install @tanstack/react-query@5.17.0
npm install react-pdf@7.7.0
npm install tailwindcss@3.4.0
```

### 2. Configure Environment

```bash
# .env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 3. Start Development Server

```bash
npm run dev
# Open http://localhost:3000/inbox
```

## Usage Examples

### Navigate to Inbox

```
http://localhost:3000/inbox
```

### Apply Filters

```
http://localhost:3000/inbox?status=PARSED&from_email=buyer@customer.com
```

### View Message Detail

```
http://localhost:3000/inbox/uuid-message-id
```

## Testing

```bash
# Component tests
npm run test

# E2E tests
npm run test:e2e

# Watch mode
npm run test:watch
```

### Component Test Example

```typescript
// tests/components/inbox/InboxTable.test.tsx
import { render, screen } from '@testing-library/react';
import { InboxTable } from '@/components/inbox/InboxTable';

test('renders inbox table with messages', () => {
  const mockData = {
    items: [
      {
        id: 'uuid',
        subject: 'Test Order',
        from_email: 'buyer@customer.com',
        status: 'PARSED',
        attachment_count: 1,
        received_at: '2025-12-27T10:00:00Z'
      }
    ]
  };

  render(<InboxTable data={mockData} />);

  expect(screen.getByText('Test Order')).toBeInTheDocument();
  expect(screen.getByText('buyer@customer.com')).toBeInTheDocument();
});
```

## Common Issues

### PDF preview not rendering
**Solution**: Install pdfjs-dist: `npm install pdfjs-dist@3.11.174`

### Inbox not loading
**Solution**: Check backend API is running on port 8000

### Filters not applying
**Solution**: Verify query params match API contract

### Images/PDFs not downloading
**Solution**: Check CORS headers in backend API
