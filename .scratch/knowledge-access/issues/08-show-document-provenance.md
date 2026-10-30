# 08: Show document provenance and failures in the console

**What to build:** Operators can trace extracted receipt facts back to case-scoped document versions and supporting pages/spans, distinguish unreadable customer evidence from parser outages, and inspect the resulting question or resolution alongside authoritative execution history.

**Blocked by:** 05: Use uploaded receipts as case-scoped evidence; 07: Inspect reproducible decision sources in the console.

**Status:** ready-for-agent

**Owners:** System 2 supplies extraction provenance and safe diagnostics; System 1 persists and exposes authorized reads; System 3 owns presentation.

**Source coverage:** Document-specific KA11–12 and expanded KA13 acceptance coverage.

- [ ] Stored run manifests include attachment versions/hashes, extraction configuration version and page/span support for accepted facts. Original and normalized values remain distinguishable where permitted.
- [ ] The console distinguishes readable, partial and unreadable evidence from technical parser/storage failure, and explains remaining material questions or conflicts.
- [ ] Document links are checked through case-scoped System 1 access; missing or changed sources display explicitly without exposing paths or cross-case information.
- [ ] Fake OCR and stored simulations are labelled. Raw attachment content and embedded instructions do not leak into progress events or alter workflow behavior.
- [ ] Offline integration coverage follows upload, extraction, clarification/reply, reassessment, execution and persisted source display for a supported receipt case.
- [ ] Combined regression checks cover unreadable/partial documents, conflicting totals, parser failure, cross-case references, malicious instructions, stale proposal rejection and duplicate-effect prevention. Assertions verify outcomes, cited versions and effects rather than wording alone.
- [ ] Expected answers and future replies remain outside runtime knowledge/model inputs. Report checks actually run and distinguish synthetic workflow correctness from legal validation.
- [ ] Open any created/updated HTML visualization in the user's browser and include a clickable link; report clearly if opening is unavailable.
