# Legal source acquisition for the airline RAG

This research collection contains **7 English legal sources with 118 extracted pages**, plus one associated Commission statement excluded from ingestion. It is separate from the application runtime and the synthetic complaint datasets. Every manifest source has `approval_status: unreviewed` and `runtime_enabled: false`.

The [source inventory](../../docs/research/legal-rag-source-inventory.md) explains scope, official references, additional acquisition seeds and legal gaps. The [source manifest](source-manifest.json) records 12 attempted sources, their URLs, acquisition results, PDF hashes and extraction metadata. Five attempted sources remain unacquired. Other sources in the research inventory have not been downloaded.

## Acquired documents

| Source | Pages | Raw PDF | Extracted page records |
|---|---:|---|---|
| EU261 original regulation | 7 | [PDF](raw/eu261.pdf) | [JSONL](extracted/eu261.pages.jsonl) |
| Commission 2024 interpretation guidelines | 36 | [PDF](raw/eu261-guidelines-2024.pdf) | [JSONL](extracted/eu261-guidelines-2024.pages.jsonl) |
| Montreal Convention | 11 | [PDF](raw/montreal-convention.pdf) | [JSONL](extracted/montreal-convention.pages.jsonl) |
| Regulation 889/2002 amending carrier liability | 4 | [PDF](raw/air-carrier-liability-amendment.pdf) | [JSONL](extracted/air-carrier-liability-amendment.pages.jsonl) |
| Accessibility Regulation 1107/2006 | 9 | [PDF](raw/accessibility.pdf) | [JSONL](extracted/accessibility.pages.jsonl) |
| Sturgeon judgment | 29 | [PDF](raw/sturgeon.pdf) | [JSONL](extracted/sturgeon.pages.jsonl) |
| Wallentin-Hermann judgment | 22 | [PDF](raw/wallentin-hermann.pdf) | [JSONL](extracted/wallentin-hermann.pages.jsonl) |

The extra `eu261-associated-document.pdf` is a Commission statement about other transport modes. Its identity and exclusion are recorded in the manifest; do not ingest every PDF by directory glob.

## Access and provenance

Direct EUR-Lex PDF requests returned non-PDF challenge responses. Downloads succeeded through the official Publications Office CELLAR service. The EU261 response listed two document streams; each was inspected before deciding which belonged in the corpus. Other attempts returned unavailable responses. Challenge pages and search snippets were not saved as legal text.

EUR-Lex describes its supported acquisition routes in [Reuse EUR-Lex content](https://eur-lex.europa.eu/content/help/data-reuse/reuse-contents-eurlex-details.html), including CELLAR and XML formats. Its [legal notice](https://eur-lex.europa.eu/content/legal-notice/legal-notice.html?locale=en) generally permits reuse of legal documents unless otherwise specified; special third-party conditions remain relevant. Preserve source attribution and identify extraction changes. Do not assume this notice licenses material from every other publisher.

PDF signatures, SHA-256 hashes, extracted first-page titles, page counts and nonempty page text were checked. Text extraction used the installed PyMuPDF version recorded per source. JSONL retains physical PDF page numbers and the original PDF hash. Page records are an acquisition format, not legally meaningful retrieval chunks. Reading order, footnotes, paragraph boundaries and completeness still need review.

## Before enabling retrieval

1. Complete missing sources, especially current ICAO liability revisions, the carrier-liability base act and judgments relevant to the supported scenarios. The old Montreal text alone contains outdated monetary limits.
2. Verify amendments, corrigenda, relevant case-law developments and application dates. Null applicability dates in the manifest mean **unknown**, not unrestricted applicability. Regulation 2026/2202 is recorded as applying from 23 October 2027; its full text was not acquired here.
3. Split reviewed text by article/paragraph or judgment paragraph, preserving exceptions and cross-references. Link supporting judgments and guidelines to the corresponding rules.
4. Assign explicit review status and supported case scope. Keep binding law, judicial interpretation, guidance and synthetic/company policies distinguishable.
5. Test retrieval for temporal errors, missing exceptions and incompatible regimes before supplying passages to decision drafting. An unreviewed or missing source cannot support automatic resolution.

The acquisition itself did not create embeddings or runtime integration. To reproduce
the separate research search index, set `OPENAI_API_KEY` locally and run
`bash scripts/setup-legal-rag.sh` from the repository root. See the
[team RAG setup guide](../../docs/development/knowledge-rag.md#team-quick-start-with-the-downloaded-legal-corpus).
The importer verifies hashes, retains page provenance and leaves review flags
unchanged. This does not create legal approval, an entitlement calculator or case
workflow integration. Customer evidence and CRM records remain outside this corpus.
