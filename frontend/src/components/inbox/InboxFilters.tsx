'use client';

import { useState } from 'react';
import { InboxFilters as FilterType } from '@/lib/api/inbox';

interface InboxFiltersProps {
  filters: FilterType;
  onChange: (filters: FilterType) => void;
}

const STATUS_OPTIONS = [
  { value: '', label: 'All Statuses' },
  { value: 'RECEIVED', label: 'Received' },
  { value: 'STORED', label: 'Stored' },
  { value: 'PARSED', label: 'Parsed' },
  { value: 'PROCESSING', label: 'Processing' },
  { value: 'FAILED', label: 'Failed' },
];

export function InboxFilters({ filters, onChange }: InboxFiltersProps) {
  const [localFilters, setLocalFilters] = useState<FilterType>(filters);

  const handleStatusChange = (status: string) => {
    const newFilters = { ...localFilters, status: status || undefined };
    setLocalFilters(newFilters);
    onChange(newFilters);
  };

  const handleSenderChange = (from_email: string) => {
    const newFilters = { ...localFilters, from_email: from_email || undefined };
    setLocalFilters(newFilters);
    onChange(newFilters);
  };

  const handleDateFromChange = (date_from: string) => {
    const newFilters = { ...localFilters, date_from: date_from || undefined };
    setLocalFilters(newFilters);
    onChange(newFilters);
  };

  const handleDateToChange = (date_to: string) => {
    const newFilters = { ...localFilters, date_to: date_to || undefined };
    setLocalFilters(newFilters);
    onChange(newFilters);
  };

  const handleSearchChange = (q: string) => {
    const newFilters = { ...localFilters, q: q || undefined };
    setLocalFilters(newFilters);
    onChange(newFilters);
  };

  const handleClearFilters = () => {
    const emptyFilters: FilterType = {};
    setLocalFilters(emptyFilters);
    onChange(emptyFilters);
  };

  const hasActiveFilters = Boolean(
    localFilters.status || localFilters.from_email || localFilters.date_from || localFilters.date_to || localFilters.q
  );

  return (
    <div className="bg-white p-4 rounded-lg border border-gray-200 mb-4 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Filters</h2>
        {hasActiveFilters && (
          <button
            onClick={handleClearFilters}
            className="text-sm text-blue-600 hover:text-blue-800 font-medium"
          >
            Clear all
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        {/* Status Filter */}
        <div>
          <label htmlFor="status-filter" className="block text-sm font-medium text-gray-700 mb-1">
            Status
          </label>
          <select
            id="status-filter"
            value={localFilters.status || ''}
            onChange={(e) => handleStatusChange(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm"
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        {/* Sender Email Filter */}
        <div>
          <label htmlFor="sender-filter" className="block text-sm font-medium text-gray-700 mb-1">
            Sender Email
          </label>
          <input
            id="sender-filter"
            type="email"
            value={localFilters.from_email || ''}
            onChange={(e) => handleSenderChange(e.target.value)}
            placeholder="buyer@customer.com"
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm"
          />
        </div>

        {/* Date From Filter */}
        <div>
          <label htmlFor="date-from-filter" className="block text-sm font-medium text-gray-700 mb-1">
            Date From
          </label>
          <input
            id="date-from-filter"
            type="date"
            value={localFilters.date_from || ''}
            onChange={(e) => handleDateFromChange(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm"
          />
        </div>

        {/* Date To Filter */}
        <div>
          <label htmlFor="date-to-filter" className="block text-sm font-medium text-gray-700 mb-1">
            Date To
          </label>
          <input
            id="date-to-filter"
            type="date"
            value={localFilters.date_to || ''}
            onChange={(e) => handleDateToChange(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm"
          />
        </div>

        {/* Search Query */}
        <div>
          <label htmlFor="search-filter" className="block text-sm font-medium text-gray-700 mb-1">
            Search
          </label>
          <input
            id="search-filter"
            type="text"
            value={localFilters.q || ''}
            onChange={(e) => handleSearchChange(e.target.value)}
            placeholder="Search subject or sender..."
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm"
          />
        </div>
      </div>
    </div>
  );
}
