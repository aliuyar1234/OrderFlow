"""Pydantic schemas for customer detection API"""

from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class DetectionSignalSchema(BaseModel):
    """Schema for a single detection signal"""
    signal_type: str = Field(..., description="Type of signal: from_email_exact, from_domain, doc_customer_number, etc.")
    value: str = Field(..., description="Extracted value (email, domain, customer number)")
    score: float = Field(..., ge=0.0, le=1.0, description="Signal confidence score")
    metadata: dict = Field(default_factory=dict, description="Additional signal metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "signal_type": "from_email_exact",
                "value": "buyer@customer-a.com",
                "score": 0.95,
                "metadata": {"email": "buyer@customer-a.com"}
            }
        }


class CandidateSchema(BaseModel):
    """Schema for a customer detection candidate"""
    customer_id: UUID = Field(..., description="Customer ID")
    customer_name: str = Field(..., description="Customer name")
    aggregate_score: float = Field(..., ge=0.0, le=1.0, description="Aggregated confidence score")
    signals: list[DetectionSignalSchema] = Field(default_factory=list, description="List of detection signals")
    signal_badges: list[str] = Field(default_factory=list, description="Human-readable signal badges for UI")

    class Config:
        json_schema_extra = {
            "example": {
                "customer_id": "550e8400-e29b-41d4-a716-446655440000",
                "customer_name": "ACME GmbH",
                "aggregate_score": 0.95,
                "signals": [
                    {
                        "signal_type": "from_email_exact",
                        "value": "buyer@acme.com",
                        "score": 0.95,
                        "metadata": {}
                    }
                ],
                "signal_badges": ["Email Match"]
            }
        }


class DetectionResultSchema(BaseModel):
    """Schema for customer detection result"""
    candidates: list[CandidateSchema] = Field(default_factory=list, description="Top candidates (max 5)")
    selected_customer_id: Optional[UUID] = Field(None, description="Auto-selected customer ID (if any)")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="Confidence of auto-selection")
    auto_selected: bool = Field(False, description="Whether customer was auto-selected")
    ambiguous: bool = Field(False, description="Whether manual selection is needed")
    reason: Optional[str] = Field(None, description="Explanation of detection result")

    class Config:
        json_schema_extra = {
            "example": {
                "candidates": [
                    {
                        "customer_id": "550e8400-e29b-41d4-a716-446655440000",
                        "customer_name": "ACME GmbH",
                        "aggregate_score": 0.95,
                        "signals": [],
                        "signal_badges": ["Email Match"]
                    }
                ],
                "selected_customer_id": "550e8400-e29b-41d4-a716-446655440000",
                "confidence": 0.95,
                "auto_selected": True,
                "ambiguous": False,
                "reason": "Auto-selected with 95.0% confidence"
            }
        }


class DetectionRequestSchema(BaseModel):
    """Schema for customer detection request"""
    from_email: Optional[str] = Field(None, description="Sender email address")
    document_text: Optional[str] = Field(None, description="Extracted document text")
    llm_hint: Optional[dict] = Field(None, description="Optional LLM customer hint")
    auto_select_threshold: float = Field(0.90, ge=0.0, le=1.0, description="Minimum score for auto-selection")
    min_gap: float = Field(0.07, ge=0.0, le=1.0, description="Minimum gap between top 2 candidates")

    class Config:
        json_schema_extra = {
            "example": {
                "from_email": "buyer@customer-a.com",
                "document_text": "Kundennr: 4711\nACME GmbH\n...",
                "auto_select_threshold": 0.90,
                "min_gap": 0.07
            }
        }


class SelectCustomerRequestSchema(BaseModel):
    """Schema for manual customer selection"""
    customer_id: UUID = Field(..., description="Selected customer ID")

    class Config:
        json_schema_extra = {
            "example": {
                "customer_id": "550e8400-e29b-41d4-a716-446655440000"
            }
        }


class SelectCustomerResponseSchema(BaseModel):
    """Schema for customer selection response"""
    success: bool = Field(..., description="Whether selection was successful")
    customer_id: UUID = Field(..., description="Selected customer ID")
    customer_name: str = Field(..., description="Selected customer name")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence after selection")
    message: str = Field(..., description="Success/error message")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "customer_id": "550e8400-e29b-41d4-a716-446655440000",
                "customer_name": "ACME GmbH",
                "confidence": 0.90,
                "message": "Customer selected successfully"
            }
        }
