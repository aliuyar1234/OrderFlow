"""LLM-based extractor for unstructured and scanned PDFs (SSOT §7.5)."""

import hashlib
import json
import logging
from typing import Any

from pydantic import ValidationError

from ai.ports import (
    LLMProviderPort,
    LLMProviderError,
    LLMTimeoutError,
    LLMRateLimitError,
)
from schemas.extraction_output import ExtractionOutput
from hallucination_guards import apply_hallucination_guards


logger = logging.getLogger(__name__)


class LLMExtractor:
    """LLM-based extractor for PDF orders.

    Implements SSOT §7.5:
    - Text extraction via LLM for irregular layouts
    - Vision extraction for scanned/image PDFs
    - JSON repair for malformed outputs (1 retry)
    - Hallucination guards (anchor check, range check, lines count check)
    - Structured output validation via Pydantic
    """

    def __init__(
        self,
        llm_provider: LLMProviderPort,
        max_lines: int = 500,
        max_qty: int = 1_000_000,
    ):
        """Initialize LLM extractor.

        Args:
            llm_provider: LLM provider implementation
            max_lines: Maximum lines allowed in extraction
            max_qty: Maximum quantity value allowed
        """
        self.llm_provider = llm_provider
        self.max_lines = max_lines
        self.max_qty = max_qty

    def extract_from_text(
        self,
        pdf_text: str,
        context: dict[str, Any],
        source_text: str | None = None,
        page_count: int | None = None,
    ) -> dict[str, Any]:
        """Extract order from PDF text using LLM.

        Args:
            pdf_text: Extracted PDF text
            context: Extraction context (from_email, subject, etc.)
            source_text: Original source text for anchor checking (defaults to pdf_text)
            page_count: Number of pages in PDF

        Returns:
            Extraction result dict with:
            - output: Validated ExtractionOutput
            - llm_result: Raw LLM result
            - input_hash: Hash for deduplication
            - status: 'SUCCEEDED' or 'FAILED'
            - error: Error details if failed

        Raises:
            LLMProviderError: For unrecoverable provider errors
        """
        source_text = source_text or pdf_text

        # Calculate input hash for deduplication
        input_hash = self._calculate_input_hash(pdf_text, context)

        try:
            # Call LLM provider
            llm_result = self.llm_provider.extract_order_from_pdf_text(
                text=pdf_text,
                context=context
            )

            # Parse and validate output
            output, validation_error = self._parse_and_validate(
                llm_result=llm_result,
                context=context,
            )

            if output is None:
                # Parsing/validation failed
                return {
                    "output": None,
                    "llm_result": llm_result,
                    "input_hash": input_hash,
                    "status": "FAILED",
                    "error": {
                        "code": "LLM_INVALID_JSON" if not llm_result.parsed_json else "LLM_SCHEMA_MISMATCH",
                        "message": validation_error or "Failed to parse LLM output",
                    }
                }

            # Apply hallucination guards
            output_dict = output.model_dump(mode="json")
            output_dict = apply_hallucination_guards(
                extraction_output=output_dict,
                source_text=source_text,
                page_count=page_count,
                max_qty=self.max_qty,
            )

            # Re-validate after guards
            try:
                output = ExtractionOutput(**output_dict)
            except ValidationError as e:
                logger.warning(f"Validation error after applying guards: {e}")
                # Continue with partially validated output

            return {
                "output": output,
                "llm_result": llm_result,
                "input_hash": input_hash,
                "status": "SUCCEEDED",
                "error": None,
            }

        except (LLMTimeoutError, LLMRateLimitError) as e:
            # Recoverable errors - log and return failed status
            logger.error(f"LLM extraction failed: {e}")
            return {
                "output": None,
                "llm_result": None,
                "input_hash": input_hash,
                "status": "FAILED",
                "error": {
                    "code": "LLM_TIMEOUT" if isinstance(e, LLMTimeoutError) else "LLM_RATE_LIMIT",
                    "message": str(e),
                }
            }

    def extract_from_images(
        self,
        images: list[bytes],
        context: dict[str, Any],
        source_text: str = "",
        page_count: int | None = None,
    ) -> dict[str, Any]:
        """Extract order from PDF images using vision LLM.

        Args:
            images: List of PNG image bytes (one per page)
            context: Extraction context
            source_text: OCR text if available for anchor checking
            page_count: Number of pages

        Returns:
            Extraction result dict (same structure as extract_from_text)

        Raises:
            LLMProviderError: For unrecoverable provider errors
        """
        # Calculate input hash from images
        images_hash = hashlib.sha256(b"".join(images)).hexdigest()
        input_hash = hashlib.sha256(
            f"{images_hash}:{json.dumps(context, sort_keys=True)}".encode()
        ).hexdigest()

        try:
            # Call vision LLM provider
            llm_result = self.llm_provider.extract_order_from_pdf_images(
                images=images,
                context=context
            )

            # Parse and validate output
            output, validation_error = self._parse_and_validate(
                llm_result=llm_result,
                context=context,
            )

            if output is None:
                return {
                    "output": None,
                    "llm_result": llm_result,
                    "input_hash": input_hash,
                    "status": "FAILED",
                    "error": {
                        "code": "LLM_INVALID_JSON" if not llm_result.parsed_json else "LLM_SCHEMA_MISMATCH",
                        "message": validation_error or "Failed to parse LLM output",
                    }
                }

            # Apply hallucination guards (with OCR text if available)
            output_dict = output.model_dump(mode="json")
            if source_text:
                output_dict = apply_hallucination_guards(
                    extraction_output=output_dict,
                    source_text=source_text,
                    page_count=page_count or len(images),
                    max_qty=self.max_qty,
                )

            # Re-validate after guards
            try:
                output = ExtractionOutput(**output_dict)
            except ValidationError as e:
                logger.warning(f"Validation error after applying guards: {e}")

            return {
                "output": output,
                "llm_result": llm_result,
                "input_hash": input_hash,
                "status": "SUCCEEDED",
                "error": None,
            }

        except (LLMTimeoutError, LLMRateLimitError) as e:
            logger.error(f"Vision LLM extraction failed: {e}")
            return {
                "output": None,
                "llm_result": None,
                "input_hash": input_hash,
                "status": "FAILED",
                "error": {
                    "code": "LLM_TIMEOUT" if isinstance(e, LLMTimeoutError) else "LLM_RATE_LIMIT",
                    "message": str(e),
                }
            }

    def _parse_and_validate(
        self,
        llm_result: Any,
        context: dict[str, Any],
    ) -> tuple[ExtractionOutput | None, str | None]:
        """Parse and validate LLM output with JSON repair if needed.

        Per SSOT §7.5.4: Attempt JSON repair once if initial parsing fails.

        Args:
            llm_result: Result from LLM provider
            context: Extraction context

        Returns:
            Tuple of (validated_output, error_message)
            If successful, error_message is None.
            If failed, validated_output is None.
        """
        raw_output = llm_result.raw_output.strip()

        # Step 1: Check if output starts with '{'
        if not raw_output.startswith("{"):
            return None, "LLM output does not start with '{'"

        # Step 2: Try parsing from llm_result.parsed_json first
        if llm_result.parsed_json:
            try:
                return ExtractionOutput(**llm_result.parsed_json), None
            except ValidationError as e:
                # Schema mismatch - try repair
                logger.warning(f"Schema validation failed: {e}")
                return self._attempt_json_repair(
                    raw_output=raw_output,
                    validation_error=str(e),
                    context=context,
                )

        # Step 3: parsed_json is None - try json.loads
        try:
            parsed = json.loads(raw_output)
        except json.JSONDecodeError as e:
            # Invalid JSON - try repair
            logger.warning(f"JSON decode failed: {e}")
            return self._attempt_json_repair(
                raw_output=raw_output,
                validation_error=str(e),
                context=context,
            )

        # Step 4: Validate parsed JSON
        try:
            return ExtractionOutput(**parsed), None
        except ValidationError as e:
            # Schema mismatch - try repair
            logger.warning(f"Schema validation failed: {e}")
            return self._attempt_json_repair(
                raw_output=raw_output,
                validation_error=str(e),
                context=context,
            )

    def _attempt_json_repair(
        self,
        raw_output: str,
        validation_error: str,
        context: dict[str, Any],
    ) -> tuple[ExtractionOutput | None, str | None]:
        """Attempt to repair invalid JSON using LLM.

        Per SSOT §7.5.4: Only one repair attempt.

        Args:
            raw_output: Invalid JSON string
            validation_error: Error message from validation
            context: Extraction context

        Returns:
            Tuple of (validated_output, error_message)
        """
        try:
            # Get schema as JSON string
            schema_json = ExtractionOutput.model_json_schema()

            # Call repair
            repair_context = {
                "schema_json": json.dumps(schema_json, indent=2),
                **context
            }

            repaired_json = self.llm_provider.repair_invalid_json(
                previous_output=raw_output,
                error=validation_error,
                context=repair_context,
            )

            # Try parsing repaired JSON
            repaired_json = repaired_json.strip()
            if not repaired_json.startswith("{"):
                return None, "Repaired output does not start with '{'"

            parsed = json.loads(repaired_json)
            validated = ExtractionOutput(**parsed)

            logger.info("Successfully repaired invalid JSON")
            return validated, None

        except json.JSONDecodeError as e:
            return None, f"JSON repair failed: {e}"
        except ValidationError as e:
            return None, f"Repaired JSON still invalid: {e}"
        except (LLMTimeoutError, LLMRateLimitError, LLMProviderError) as e:
            return None, f"JSON repair call failed: {e}"

    def _calculate_input_hash(self, text: str, context: dict[str, Any]) -> str:
        """Calculate hash for deduplication.

        Hash includes:
        - PDF text
        - from_email
        - subject
        - default_currency

        Args:
            text: PDF text
            context: Extraction context

        Returns:
            SHA256 hash hex string
        """
        hash_input = {
            "text": text,
            "from_email": context.get("from_email"),
            "subject": context.get("subject"),
            "default_currency": context.get("default_currency"),
        }
        return hashlib.sha256(
            json.dumps(hash_input, sort_keys=True).encode()
        ).hexdigest()
