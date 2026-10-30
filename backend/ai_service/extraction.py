"""Small synthetic-document extractor, never an entitlement/policy interpreter.

Consumes only verified System 1 reader results. Spans are zero-based, end-exclusive
Unicode character offsets within the numbered page, not PDF byte offsets.
Only explicit labelled fields are supported; arbitrary prose remains untrusted.
"""
from datetime import date
from decimal import Decimal
import re
from typing import Literal, Protocol
from dataclasses import dataclass
from io import BytesIO

from backend.ai_service.evidence import AttachmentResult, EvidenceScope
from backend.contracts import Contract, SourceRef, TechnicalError


class Provenance(Contract):
    source: SourceRef
    content_hash: str
    page: int
    span_start: int
    span_end: int
    original_value: str
    supporting_text: str


class ExtractionCandidate(Contract):
    name: Literal['receipt_amount_minor', 'receipt_currency', 'receipt_date', 'expense_purpose']
    value: str | int
    provenance: Provenance


class ExtractionResult(Contract):
    scope: EvidenceScope
    status: Literal['readable', 'partial', 'unreadable', 'parser_failure']
    candidates: tuple[ExtractionCandidate, ...] = ()
    simulation: bool = False
    configuration_version: str = 'synthetic-labelled-fields-v1'
    error: TechnicalError | None = None


class PDFParser(Protocol):
    def pages(self, content: bytes) -> tuple[str, ...]: ...


class PypdfParser:
    """Optional lazy parser; install pypdf>=5,<7 to enable text PDFs."""
    def pages(self, content: bytes) -> tuple[str, ...]:
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(content), strict=True)
        if reader.is_encrypted:
            raise ValueError('Encrypted PDF unsupported')
        if len(reader.pages) > 50:
            raise ValueError('PDF page limit exceeded')
        return tuple(page.extract_text() or '' for page in reader.pages)


class OCRAdapter(Protocol):
    simulation: bool
    def pages(self, content: bytes, media_type: str) -> tuple[str, ...]: ...


@dataclass(frozen=True)
class FakeOCR:
    """Explicit synthetic OCR output, with no image interpretation or I/O."""
    text_pages: tuple[str, ...] = ()
    simulation: bool = True

    def pages(self, content: bytes, media_type: str) -> tuple[str, ...]:
        return self.text_pages


class DocumentExtractor:
    """Labelled synthetic receipts use exactly two decimal minor-unit places.

    Amount extraction is independent of currency. Only EUR/USD/GBP are supported;
    absent/unsupported currency must remain a gap before financial use.
    """
    def __init__(self, *, ocr: OCRAdapter | None = None, pdf_parser: PDFParser | None = None):
        self.ocr = ocr
        self.pdf_parser = pdf_parser or PypdfParser()

    def extract(self, attachment: AttachmentResult) -> ExtractionResult:
        if attachment.status == 'unavailable':
            return ExtractionResult(scope=attachment.scope, status='parser_failure', error=attachment.error)
        if attachment.status == 'scope_violation':
            return self._failure(attachment, 'ATTACHMENT_SCOPE_VIOLATION', False)
        if attachment.status != 'found':
            return ExtractionResult(scope=attachment.scope, status='unreadable')
        if attachment.reference.media_type not in {'text/plain', 'application/pdf', 'image/png', 'image/jpeg'}:
            return ExtractionResult(scope=attachment.scope, status='unreadable')
        if len(attachment.content) > 5 * 1024 * 1024:
            return ExtractionResult(scope=attachment.scope, status='unreadable')
        simulation = False
        try:
            if attachment.reference.media_type == 'text/plain':
                pages = (attachment.content.decode('utf-8'),)
            elif attachment.reference.media_type == 'application/pdf':
                try:
                    pages = self.pdf_parser.pages(attachment.content)
                except ImportError:
                    return self._failure(attachment, 'PDF_ADAPTER_UNCONFIGURED', False)
                if any(not text.strip() for text in pages) or not pages:
                    if self.ocr is None:
                        return self._failure(attachment, 'OCR_ADAPTER_UNCONFIGURED', False)
                    simulation = self.ocr.simulation
                    ocr_pages = self.ocr.pages(attachment.content, attachment.reference.media_type)
                    if len(ocr_pages) != len(pages):
                        raise ValueError('OCR page alignment failure')
                    pages = tuple(text if text.strip() else ocr_pages[i] for i, text in enumerate(pages))
            else:
                if self.ocr is None:
                    return self._failure(attachment, 'OCR_ADAPTER_UNCONFIGURED', False)
                simulation = self.ocr.simulation
                pages = self.ocr.pages(attachment.content, attachment.reference.media_type)
            if len(pages) > 50 or sum(len(text) for text in pages) > 500_000:
                return self._failure(attachment, 'EXTRACTION_OUTPUT_LIMIT', False, simulation)
            candidates = [c for page, text in enumerate(pages, 1)
                          for c in self._fields(attachment, text, page)]
        except UnicodeDecodeError:
            return ExtractionResult(scope=attachment.scope, status='unreadable')
        except Exception:
            return self._failure(attachment, 'EXTRACTION_PARSER_FAILURE', True, simulation)
        names = {c.name for c in candidates}
        conflict = any(len({c.value for c in candidates if c.name == name}) > 1 for name in names)
        status = 'readable' if not conflict and names == {'receipt_amount_minor', 'receipt_currency', 'receipt_date', 'expense_purpose'} else 'partial' if any(text.strip() for text in pages) else 'unreadable'
        return ExtractionResult(scope=attachment.scope, status=status, candidates=tuple(candidates), simulation=simulation)

    @staticmethod
    def _failure(attachment, code, retryable, simulation=False):
        return ExtractionResult(scope=attachment.scope, status='parser_failure', simulation=simulation,
            error=TechnicalError(code=code, message='Document extraction could not be completed.', retryable=retryable))

    def _fields(self, attachment, text, page):
        candidates = []
        for match in re.finditer(r'(?m)^(Total|Currency|Date|Purpose):[ \t]*([^\r\n]+)', text):
            label, raw = match.group(1, 2)
            if label == 'Total':
                if not re.fullmatch(r'[0-9]{1,9}(?:[.,][0-9]{2})?', raw):
                    continue
                name, value = 'receipt_amount_minor', int(Decimal(raw.replace(',', '.')) * 100)
            elif label == 'Currency':
                if raw not in {'EUR', 'USD', 'GBP'}:
                    continue
                name, value = 'receipt_currency', raw
            elif label == 'Date':
                if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', raw):
                    continue
                try:
                    value = date.fromisoformat(raw).isoformat()
                except ValueError:
                    continue
                name = 'receipt_date'
            else:
                # Closed synthetic vocabulary: document instructions are not facts.
                if raw.lower() not in {'meals', 'hotel', 'transport'}:
                    continue
                name, value = 'expense_purpose', raw.lower()
            candidates.append(ExtractionCandidate(name=name, value=value, provenance=Provenance(
                source=attachment.source, content_hash=attachment.content_hash, page=page,
                span_start=match.start(2), span_end=match.end(2), original_value=raw,
                supporting_text=match.group())))
        return candidates
