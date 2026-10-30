# 05: Use uploaded receipts as case-scoped evidence

**What to build:** A synthetic receipt upload becomes sourced evidence used in reassessment and authoritative execution. A readable document can complete an expense case; partial or unreadable evidence produces a focused question, while extraction infrastructure failures remain failed runs.

**Blocked by:** 04: Complete the three offline flows through authoritative execution.

**Status:** ready-for-agent

**Owners:** System 1 owns upload storage and scoped reads; System 2 owns extraction and reconciliation; System 3 connects upload controls through System 1.

**Source coverage:** KA04–05 and document integration in KA08/13.

- [ ] Opaque attachment references resolve through a System 1 read adapter only after case-membership checks. Arbitrary paths/URLs, traversal and cross-case reads are rejected; System 2 has no unrestricted filesystem or database access.
- [ ] Supported formats, verified media metadata and size limits are explicit. Missing files, unsupported formats, oversized files and storage outages have distinct outcomes.
- [ ] The same attachment ID/version resolves reproducibly; changed bytes receive a new version or hash.
- [ ] Text and text-based PDF extraction returns original values, normalized candidates, extraction status and page/span provenance. Images/scanned PDFs use a replaceable fake OCR adapter explicitly labelled simulated.
- [ ] Amount, currency, date and purpose are independently represented. Currency is never guessed; validated monetary conversion uses integer minor units. Attachment metadata alone is not extracted evidence.
- [ ] Readable, partial, unreadable and parser-failure outcomes stay distinct. Missing/illegible customer evidence asks a material question; parser/storage outages produce FAILED with no proposal or effects.
- [ ] Accepted facts resolve to the attachment version and supporting text/page. Conflicting totals survive reconciliation, and embedded instructions cannot change policy, trigger tools or enter the shared knowledge registry.
- [ ] An upload/reply round trip on the same case can resolve a supported expense through System 1. Offline tests cover clear/partial receipts, conflicting totals, unreadable scans, parser failure, malicious instructions, cross-case access, media mismatch and size limits.
