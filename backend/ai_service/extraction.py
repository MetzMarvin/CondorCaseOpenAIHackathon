"""Small synthetic-document extractor, never an entitlement/policy interpreter.

Consumes only verified System 1 reader results. Spans are zero-based, end-exclusive
Unicode character offsets within the numbered page, not PDF byte offsets.
Supports synthetic labels and bounded customer prose; claims are not authority.
"""
from datetime import date
from decimal import Decimal
from hashlib import sha256
import re
from typing import Literal, Protocol
from dataclasses import dataclass
from io import BytesIO

from backend.ai_service.evidence import AttachmentResult, EvidenceScope
from backend.contracts import Contract, Message, SourceRef, TechnicalError


class Provenance(Contract):
    source: SourceRef
    content_hash: str
    page: int
    span_start: int
    span_end: int
    original_value: str
    supporting_text: str


class ExtractionCandidate(Contract):
    name: Literal['receipt_amount_minor', 'receipt_currency', 'receipt_date', 'expense_purpose',
                  'booking_reference', 'baggage_reference', 'flight_number', 'flight_date']
    value: str | int
    provenance: Provenance


class ExtractionResult(Contract):
    scope: EvidenceScope
    status: Literal['readable', 'partial', 'unreadable', 'parser_failure']
    candidates: tuple[ExtractionCandidate, ...] = ()
    simulation: bool = False
    configuration_version: str = 'synthetic-fields-v2'
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
                          for c in self._fields(text, page, attachment.source, attachment.content_hash)]
        except UnicodeDecodeError:
            return ExtractionResult(scope=attachment.scope, status='unreadable')
        except Exception:
            return self._failure(attachment, 'EXTRACTION_PARSER_FAILURE', True, simulation)
        names = {c.name for c in candidates}
        conflict = any(len({c.value for c in candidates if c.name == name}) > 1 for name in names)
        status = 'readable' if not conflict and {'receipt_amount_minor', 'receipt_currency', 'receipt_date', 'expense_purpose'} <= names else 'partial' if any(text.strip() for text in pages) else 'unreadable'
        return ExtractionResult(scope=attachment.scope, status=status, candidates=tuple(candidates), simulation=simulation)

    @staticmethod
    def _failure(attachment, code, retryable, simulation=False):
        return ExtractionResult(scope=attachment.scope, status='parser_failure', simulation=simulation,
            error=TechnicalError(code=code, message='Document extraction could not be completed.', retryable=retryable))

    @staticmethod
    def _candidate(name, value, match, group, page, source, content_hash):
        return ExtractionCandidate(name=name, value=value, provenance=Provenance(
            source=source, content_hash=content_hash, page=page,
            span_start=match.start(group), span_end=match.end(group),
            original_value=match.group(group), supporting_text=match.group()))

    def _fields(self, text, page, source, content_hash):
        candidates = []
        # Generator DATE comes from flight_date, even on its receipts.
        generated = 'DEMO - SYNTHETIC TEST DOCUMENT' in text
        pattern = r'(?im)^[ \t]*(Total(?:[ \t]+(?P<currency>[A-Z]{3}))?|Currency|Date|Receipt date|Purpose|Item|Booking|Booking reference|Flight|PIR reference|Bag tag):[ \t]*(?P<value>[^\r\n]*?)[ \t]*$'
        for match in re.finditer(pattern, text):
            label, raw = match.group(1).lower(), match.group('value')
            if match.group('currency'):
                currency = match.group('currency').upper()
                if currency in {'EUR', 'USD', 'GBP'}:
                    candidates.append(self._candidate('receipt_currency', currency,
                        match, 'currency', page, source, content_hash))
            if label.startswith('total'):
                if not re.fullmatch(r'[0-9]{1,9}(?:[.,][0-9]{2})?', raw):
                    continue
                name, value = 'receipt_amount_minor', int(Decimal(raw.replace(',', '.')) * 100)
            elif label == 'currency':
                if raw.upper() not in {'EUR', 'USD', 'GBP'}:
                    continue
                name, value = 'receipt_currency', raw.upper()
            elif label in {'date', 'receipt date'}:
                if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', raw):
                    continue
                try:
                    value = date.fromisoformat(raw).isoformat()
                except ValueError:
                    continue
                name = 'flight_date' if generated and label == 'date' else 'receipt_date'
            elif label in {'purpose', 'item'}:
                if raw.lower() not in {'meals', 'hotel', 'transport', 'essential toiletries'}:
                    continue
                name, value = 'expense_purpose', raw.lower()
            else:
                if not re.fullmatch(r'[A-Z0-9][A-Z0-9-]{2,39}', raw):
                    continue
                name = {'booking': 'booking_reference', 'booking reference': 'booking_reference',
                        'flight': 'flight_number', 'pir reference': 'baggage_reference',
                        'bag tag': 'baggage_reference'}[label]
                value = raw
            candidates.append(self._candidate(name, value, match, 'value',
                                              page, source, content_hash))
        return candidates

    def extract_message(self, message: Message, scope: EvidenceScope) -> ExtractionResult:
        """Bounded customer claims, with body offsets and snapshot-version sources.

        Claimed spending is deliberately not promoted to receipt evidence.
        """
        text = message.body
        if len(text) > 500_000:
            return ExtractionResult(scope=scope, status='parser_failure', error=TechnicalError(
                code='EXTRACTION_OUTPUT_LIMIT', message='Message extraction limit exceeded.', retryable=False))
        source = SourceRef(source_id=message.message_id, version=str(scope.case_version))
        content_hash = sha256(text.encode('utf-8')).hexdigest()
        identifier = r'([A-Z0-9][A-Z0-9-]{2,39})(?=[.,;!?]?(?:\s|$))'
        patterns = (
            ('booking_reference', r'(?i:my booking reference is|booking reference:)[ \t]+' + identifier),
            ('baggage_reference', r'(?i:my baggage reference is|my PIR reference is|PIR reference:|my bag tag is|bag tag:)[ \t]+' + identifier),
            ('flight_number', r'\bFlight[ \t]+' + identifier),
            ('flight_date', r'\bFlight[ \t]+[A-Z0-9-]+ from [A-Z]{3} to [A-Z]{3} was on ([0-9]{4}-[0-9]{2}-[0-9]{2})(?=[.,;!?]?(?:\s|$))'),
        )
        candidates = []
        for name, pattern in patterns:
            for match in re.finditer(pattern, text):
                value = match.group(1)
                if name == 'flight_date':
                    try:
                        value = date.fromisoformat(value).isoformat()
                    except ValueError:
                        continue
                candidates.append(self._candidate(name, value, match, 1, 1, source, content_hash))
        return ExtractionResult(scope=scope, status='partial' if text.strip() else 'unreadable',
                                candidates=tuple(candidates))
