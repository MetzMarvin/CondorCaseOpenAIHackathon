from typing import Literal
from .contracts import Contract, Fact, ExtractedDocument, PreparationDiagnostic


class LookupResult(Contract):
    status: Literal['MATCHED', 'NOT_FOUND', 'AMBIGUOUS', 'NOT_ATTEMPTED']
    customer_context: tuple[Fact, ...] = ()
    booking_context: tuple[Fact, ...] = ()
    flight_context: tuple[Fact, ...] = ()


class PreparedClaim(Contract):
    case_id: str
    case_version: int
    mode: Literal['offline', 'live']
    messages: list[dict]
    facts: tuple[Fact, ...] = ()
    documents: tuple[ExtractedDocument, ...] = ()
    lookup: LookupResult
    diagnostics: tuple[PreparationDiagnostic, ...] = ()


class ExtractedValue(Contract):
    name: Literal['customer_id', 'booking_reference', 'flight_number', 'travel_date', 'origin', 'destination', 'customer_statement']
    value: str
    quote: str


class Extraction(Contract):
    values: list[ExtractedValue]


class Transcription(Contract):
    text: str
