# Legal RAG source inventory for airline complaints

Research date: **2026-10-30**. Scope: official EU/international and German sources for System 2 knowledge preparation. This is a source inventory, not an implemented entitlement engine or legal approval. Existing scenario context is in [airline legal checks](airline-legal-checks.md). No interfaces or execution permissions change.

## What is usable now

The strongest starting corpus combines the legislation with selected CJEU judgments; the statute alone misses important interpretation. Keep Commission guidance as a navigational and explanatory layer. The source identifiers below are suitable acquisition seeds, but **an indexed search passage is not a complete document ready for ingestion**.

Research access labels describe this investigation, independently of the acquisition artifacts under `data/legal/`:

- **Direct**: official page content was returned by a browser open.
- **Indexed**: official publisher search results returned relevant text or metadata; a full source was not acquired in this research branch.
- **Blocked**: direct opening returned an anti-bot page or timeout. This can coexist with Indexed.

Local download status is recorded separately in the [source manifest](../../data/legal/source-manifest.json) and [acquisition README](../../data/legal/README.md). Seven official CELLAR English PDFs were acquired: EU261, the 2024 EU261 guidelines, Montreal Convention, 889/2002, 1107/2006, Sturgeon and Wallentin-Hermann. Their 118 pages were extracted into page-referenced JSONL and their titles and hashes checked. Five other attempted sources remain unacquired. The ICAO table was verified in indexed official text, but its direct open returned 404; it is not a downloaded corpus artifact. Do not embed these research notes as though they were the underlying law.

## Binding instruments and official interpretation

| Source / stable identifier | Coverage and retrieval units | Research access / caveat |
|---|---|---|
| [Regulation (EC) 261/2004](https://eur-lex.europa.eu/eli/reg/2004/261/oj/eng), CELEX `32004R0261` | Articles 2–3: definitions/scope; 4–7: denied boarding, cancellation, delay and compensation; 8–9: reimbursement/rerouting and care; 10–16: downgrading, vulnerable passengers, information and enforcement. Keep each article with its paragraphs and cross-references. | Indexed; direct ELI blocked. Acquire DE and EN plus applicable corrigenda/consolidation metadata. |
| [Commission Notice C/2024/5687](https://eur-lex.europa.eu/eli/C/2024/5687/oj/eng/pdf), 25 September 2024 | Interpretative guidelines for EU261 and 2027/97. Useful thematic map and case-law discovery source; chunk by numbered section and preserve footnotes. | Indexed; direct PDF endpoint returned anti-bot HTML. Guidance does not replace the regulation or Court judgments. |
| [Regulation (EU) 2026/2202](https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=OJ%3AL_202602202), CELEX `32026R2202` | Amendment to EU261 and 2027/97; retain Article 3 and amendment relationships. | Indexed official Article 3 verified; direct HTML blocked. **Future application: 23 October 2027.** |
| [Montreal Convention 1999](https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX%3A22001A0718%2801%29), CELEX `22001A0718(01)` | Acquire Articles 1, 17–24, 29, 31, 33, 35 and relevant carrier provisions. Covers scope, passenger/baggage liability, defenses, limits, written complaints and actions. | Indexed selected passages; direct text blocked. Complete article verification and route-specific treaty applicability remain prerequisites. |
| [ICAO 2024 revised liability limits](https://www.icao.int/secretariat/legal/LEB%20Treaty%20Collection%20Documents/2024_Revised_Limits_of_Liability_Under_the_Montreal_Convention_of_1999_en.pdf) | Official depositary table linking Articles 21/22 to SDR limits effective 28 December 2024. | Indexed table verified. Baggage: **1,519 SDR per passenger**; passenger delay: 6,303 SDR; Article 21 first tier: 151,880 SDR; cargo: 26 SDR/kg. |
| [Regulation (EC) 2027/97, 30 May 2002 consolidation](https://eur-lex.europa.eu/eli/reg/1997/2027/2002-05-30/eng), CELEX `01997R2027-20020530` | Article 3 applies relevant Montreal liability provisions to Community air carriers; also collect scope, advances and information duties. | Indexed Article 3 verified; direct dated ELI blocked. Consolidation is a research aid; retain underlying acts, including amendment 889/2002. |
| [Regulation (EC) 1107/2006](https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX%3A32006R1107), CELEX `32006R1107` | Accessibility: refusal exceptions, airport/carrier responsibilities, assistance and mobility equipment. Preserve Articles 3–10 and Annexes I–II as linked units. | Indexed relevant text verified; direct ELI blocked. Article 7(3) requires reasonable efforts even without prior notification; no blanket refusal because 48-hour notice was absent. |
| [Commission accessibility guidelines C/2024/5992](https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX%3A52024XC05992) | Interpretation of 1107/2006, including notification, connecting assistance and seating. | Indexed passages verified; supplementary guidance, not an independent compensation tariff. |
| [GDPR, Regulation (EU) 2016/679](https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng), CELEX `32016R0679` | Acquire Articles 5–6, 9, 12–22, 25, 28, 32, 35 and transfer provisions as relevant. Separate data-governance knowledge from compensation entitlement retrieval. | Indexed Article 22 safeguards verified; direct ELI blocked. Full processing-purpose/legal-basis and automated-decision analysis remains outside this inventory. |

The [2026 amendment's Article 3](https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=OJ%3AL_202602202) distinguishes entry into force from application. Its publication is 2 October 2026; the indexed metadata records entry into force on 22 October 2026 and application on **23 October 2027**. Store both dates and exclude future substantive rules from October 2026 incident assessments. An “in force” status or recent publication is insufficient to select a rule.

The [ICAO table](https://www.icao.int/secretariat/legal/LEB%20Treaty%20Collection%20Documents/2024_Revised_Limits_of_Liability_Under_the_Montreal_Convention_of_1999_en.pdf) must accompany the older Convention text: its original amounts are not the revised limits. A limit is not a flat award; do not turn 1,519 SDR into an automatic payment or a permanent euro value. Special declarations, exceptions, actual loss and the relevant conversion rule need separate assessment.

## Minimum CJEU seed set

These are judgment identifiers, not Advocate General opinions or press releases. All below were found through official EUR-Lex indexed judgment text or official summaries; the acquisition task downloaded Sturgeon and Wallentin-Hermann separately. Full-text acquisition for the other seeds and subsequent-treatment checking remain necessary. Summaries should be labeled as summaries and replaced by the judgment for production reasoning.

| Judgment | Verified relevance | Source and acquisition identifier |
|---|---|---|
| Sturgeon, joined C-402/07 and C-432/07, 19 November 2009 | Arrival delay of at least three hours can trigger Article 7 compensation, subject to the applicable conditions/defense. | [Judgment](https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX%3A62007CJ0402), `62007CJ0402`, ECLI:EU:C:2009:716; paragraph 61 and operative part. |
| Nelson, joined C-581/10 and C-629/10, 23 October 2012 | Long-delay compensation and compatibility with Montreal; companion authority to Sturgeon. | [Judgment](https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX%3A62010CJ0581), `62010CJ0581`. Indexed title/context verified; acquire full reasoning. |
| Wallentin-Hermann, C-549/07, 22 December 2008 | Technical problems are not automatically extraordinary; assess inherent activity, actual control and reasonable measures. | [Judgment](https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX%3A62007CJ0549), `62007CJ0549`, ECLI:EU:C:2008:771; paragraphs 24–27, 39–43. |
| Folkerts, C-11/11, 26 February 2013 | Direct connections: final-destination delay matters even when departure delay does not meet Article 6 thresholds. | [Judgment](https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX%3A62011CJ0011), `62011CJ0011`, ECLI:EU:C:2013:106; operative part. |
| Germanwings v Henning, C-452/13, 4 September 2014 | Arrival is opening at least one aircraft door with passengers permitted to leave, not touchdown. | [Judgment](https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX%3A62013CJ0452), `62013CJ0452`, ECLI:EU:C:2014:2141; paragraphs 23–27 and operative part. |
| McDonagh, C-12/11, 31 January 2013 | Extraordinary circumstances do not remove care duties; replacement care expenses must satisfy necessity, appropriateness and reasonableness. | [Judgment](https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX%3A62011CJ0012), `62011CJ0012`, ECLI:EU:C:2013:43; paragraph 66 and operative part. |
| Cuadrench Moré, C-139/11, 22 November 2012 | EU261 Articles 5/7 action deadlines follow national limitation rules; Montreal's two-year action period is not imported into these claims. | [Judgment](https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX%3A62011CJ0139), `62011CJ0139`; paragraphs 25–29. |

This set does **not** exhaust technical faults, strikes, weather, bird strikes, carrier substitutions, connecting flights, cancellations brought forward, or rerouting case law. Retrieve the guideline's cited cases and check later decisions before enabling those fact patterns. A cause label in an operations record cannot substitute for the legal test and supporting facts.

## German limitation and dispute resolution

| Source | Use and access result |
|---|---|
| [BGB §195](https://www.gesetze-im-internet.de/bgb/__195.html) and [§199](https://www.gesetze-im-internet.de/bgb/__199.html) | Direct. Ordinary limitation is three years; §199 ties its ordinary start to year-end, claim accrual and relevant knowledge conditions. Do not calculate solely from a flight date without checking governing law and exceptions. |
| [BGB §203](https://www.gesetze-im-internet.de/bgb/__203.html), [§204](https://www.gesetze-im-internet.de/bgb/__204.html) | Negotiation/legal-proceeding suspension sources to acquire with limitation rules. §203 direct; §204 direct open timed out. No complete suspension calculator verified. |
| [LuftVG §57b](https://www.gesetze-im-internet.de/luftvg/__57b.html), within [LuftVG](https://www.gesetze-im-internet.de/luftvg/) | §57b direct. Identifies covered consumer payment disputes and ADR conditions, including a €5,000 baseline with provision for higher claims under §57 rules. Acquire §§57–57d together before routing. |
| [VSBG §36](https://www.gesetze-im-internet.de/vsbg/__36.html) and [§37](https://www.gesetze-im-internet.de/vsbg/__37.html) | §36 direct; §37 indexed title, direct timeout. Information duties before/after disputes are separate acquisition units; exceptions and air-transport-specific provisions require review. |

These government-hosted consolidated pages are practical text sources. Preserve their revision metadata and use the promulgated Federal Law Gazette text for historical/version disputes. Airline participation, competent ADR body, current contact details, procedural rules and the complaint's admissibility have **not** been verified. Do not invent an ADR destination or promise that filing always suspends limitation.

## Corpus design and review gates

Recommended authority handling: first select applicable jurisdiction, regime and event-date version; then retrieve the binding instrument together with controlling judicial interpretation. Use Commission guidance to explain and find authorities. Keep regulator FAQs, airline conditions and internal goodwill policies in separately labeled collections. Airline policy must not silently override statutory rights. This is a retrieval design recommendation, not a universal conflict-of-laws algorithm.

For every acquired document record: stable source ID, publisher, document type, CELEX/ECLI/ELI where present, canonical and actual download URLs, language, publication date, entry-into-force date, application interval, consolidation date, retrieval timestamp, content hash, MIME type, parser version, review state and supersession links. For every chunk retain article/paragraph or judgment paragraph, heading, neighboring context, exceptions and cross-references. Pair DE/EN by identifier; do not label a model translation as official German text.

Before embedding, reject robot pages and empty/error downloads; verify expected title and identifier in extracted text. Separate normative articles, recitals, operative judgments, case facts, summaries and editorial metadata. Cache accepted source bytes so a demo remains reproducible without live model or network access. Search indexing alone verifies discoverability and selected passages; it does not establish a complete, checksum-pinned corpus.

Proposed retrieval checks include a pre/post-23-October-2027 question, baggage loss versus flat EU261 compensation, care despite an extraordinary-circumstance defense, final-destination versus departure delay, door-open versus touchdown time, German limitation versus Montreal action/complaint deadlines, and accessibility without advance notice. These checks are proposed; none was executed as an application test in this research task.

Remaining gaps: full source acquisition/validation; treaty party status and applicability; EEA/Swiss/UK and non-EU routes; package travel; jurisdiction and governing law; later case treatment; SDR conversion; death/injury exceptions; GDPR deployment assessment; airline-specific ADR details; current conditions of carriage; and any post-2024 guidance updates. Missing source bytes are a technical data gap, not evidence that a customer's claim fails. System 1 must still supply case-scoped itinerary, operating carrier, dates, cause/arrival records, evidence and prior payments; System 2 cannot establish those facts from legal retrieval.
