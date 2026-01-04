/**
 * Confidence indicator component
 * Displays confidence score with color-coded progress bar
 */

import React from 'react'

interface ConfidenceIndicatorProps {
  score: number // 0-1 range
  label?: string
  showPercentage?: boolean
  className?: string
}

export function ConfidenceIndicator({
  score,
  label,
  showPercentage = true,
  className = '',
}: ConfidenceIndicatorProps) {
  const percentage = Math.round(score * 100)

  const getColorClass = (score: number) => {
    if (score >= 0.9) return 'bg-green-500'
    if (score >= 0.75) return 'bg-blue-500'
    if (score >= 0.5) return 'bg-yellow-500'
    return 'bg-red-500'
  }

  const getTextColorClass = (score: number) => {
    if (score >= 0.9) return 'text-green-700'
    if (score >= 0.75) return 'text-blue-700'
    if (score >= 0.5) return 'text-yellow-700'
    return 'text-red-700'
  }

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      {label && <span className="text-sm text-gray-600">{label}:</span>}

      <div className="flex-1 min-w-[80px]">
        <div className="h-2 w-full bg-gray-200 rounded-full overflow-hidden">
          <div
            className={`h-full transition-all ${getColorClass(score)}`}
            style={{ width: `${percentage}%` }}
          />
        </div>
      </div>

      {showPercentage && (
        <span className={`text-sm font-medium ${getTextColorClass(score)}`}>
          {percentage}%
        </span>
      )}
    </div>
  )
}

interface ConfidenceBreakdownProps {
  overall: number
  extraction: number
  customer: number
  matching: number
  className?: string
}

export function ConfidenceBreakdown({
  overall,
  extraction,
  customer,
  matching,
  className = '',
}: ConfidenceBreakdownProps) {
  return (
    <div className={`space-y-2 ${className}`}>
      <ConfidenceIndicator score={overall} label="Overall" />
      <div className="pl-4 space-y-1 text-xs">
        <ConfidenceIndicator score={extraction} label="Extraction" />
        <ConfidenceIndicator score={customer} label="Customer" />
        <ConfidenceIndicator score={matching} label="Matching" />
      </div>
    </div>
  )
}
