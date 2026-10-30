# Airline complaint datasets, legal framework and Condor processes

Research notes for the AIWeek hackathon. Scope: input data, reference data, legal sources and
Condor's public process pages for an AI pipeline that handles Condor passenger complaints
(delay, cancellation, denied boarding, downgrade, baggage, refunds). Researched 2026-10-30.

Convention: every claim links to the source it was checked against. Items marked
**[unverified]** could not be confirmed against a primary source during this research.
Items marked **[practice]** are standard practitioner guidance written by the author
of these notes, not quoted from a source.

No datasets were downloaded into the repo. Metadata was read through the Kaggle API
(`/api/v1/datasets/view/...`) and the Hugging Face datasets-server (`/info`, `/statistics`).

---

## 1. Complaint text datasets

### 1.1 Comparison

| Dataset | Size / language | Fields and labels | Licence (as stated by the host) | Download | Fit |
|---|---|---|---|---|---|
| [Twitter US Airline Sentiment (Kaggle, crowdflower)](https://www.kaggle.com/datasets/crowdflower/twitter-airline-sentiment), HF mirror [`osanseviero/twitter-airline-sentiment`](https://huggingface.co/datasets/osanseviero/twitter-airline-sentiment) | 14,640 tweets, English, Feb 2015, 6 US airlines; `Tweets.csv` 3.4 MB + SQLite | `tweet_id, airline_sentiment, airline_sentiment_confidence, negativereason, negativereason_confidence, airline, airline_sentiment_gold, name, negativereason_gold, retweet_count, text, tweet_coord, tweet_created, tweet_location, user_timezone` ([HF datasets-server info](https://datasets-server.huggingface.co/info?dataset=osanseviero/twitter-airline-sentiment)). `negativereason` counts: Customer Service Issue 2,910, Late Flight 1,665, Can't Tell 1,190, Cancelled Flight 847, Lost Luggage 724, Bad Flight 580, Flight Booking Problems 529, Flight Attendant Complaints 481, longlines 178, Damaged Luggage 74 ([HF statistics](https://datasets-server.huggingface.co/statistics?dataset=osanseviero/twitter-airline-sentiment&config=default&split=train)) | Kaggle: **CC BY-NC-SA 4.0** (Kaggle API `licenseName`); HF mirror tag `cc-by-nc-sa-4.0`. The Kaggle reformatting code is MIT ([GitHub](https://github.com/benhamner/crowdflower-airline-twitter-sentiment)) | `kaggle datasets download crowdflower/twitter-airline-sentiment` or `load_dataset("osanseviero/twitter-airline-sentiment")` | **Medium.** Real, short, noisy complaints with a usable complaint-reason label (delay, cancellation, lost/damaged luggage). US context, no EU261 facts (no flight numbers, delay minutes), tweets only. Non-commercial + share-alike. |
| [Bitext travel](https://huggingface.co/datasets/bitext/Bitext-travel-llm-chatbot-training-dataset) | 31,658 instruction/response pairs, English | `instruction, intent, category, tags, response`; 33 intents / 11 categories, incl. `get_refund`, `cancel_flight`, `change_flight`, `check_baggage_allowance`, `check_cancellation_fee`, `human_agent`. No delay, compensation or complaint intent ([card](https://huggingface.co/datasets/bitext/Bitext-travel-llm-chatbot-training-dataset)) | "Community Data License Agreement (CDLA) Sharing 1.0" ([card](https://huggingface.co/datasets/bitext/Bitext-travel-llm-chatbot-training-dataset)) | `load_dataset("bitext/Bitext-travel-llm-chatbot-training-dataset")` | **Medium-low.** Synthetic, clean, intent-labelled; good for intent routing (refund vs. rebooking vs. human agent). Requests, not complaints; no legal facts. |
| [Bitext customer support](https://huggingface.co/datasets/bitext/Bitext-customer-support-llm-chatbot-training-dataset) | 26,872 pairs, English | `flags, instruction, category, intent, response`; includes `FEEDBACK/complaint`, `REFUND/check_refund_policy`, `REFUND/track_refund` ([card](https://huggingface.co/datasets/bitext/Bitext-customer-support-llm-chatbot-training-dataset)) | `cdla-sharing-1.0` (card metadata) | `load_dataset("bitext/Bitext-customer-support-llm-chatbot-training-dataset")` | **Low.** Generic e-commerce. Useful only for tone and noise variants (`flags`: colloquial, typos, offensive). |
| [Customer support tickets, Tobi-Bueck (HF)](https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets); Kaggle variant [`tobiasbueck/multilingual-customer-support-tickets`](https://www.kaggle.com/datasets/tobiasbueck/multilingual-customer-support-tickets) | HF: 61,765 tickets, **de 33,504 / en 28,261** ([statistics](https://datasets-server.huggingface.co/statistics?dataset=Tobi-Bueck/customer-support-tickets&config=default&split=train)) | `subject, body, answer, type, queue, priority, language, version, tag_1..tag_8`; one queue is `Travel & Transportation/Air Travel` (300 rows, all languages) | HF card: **`cc-by-nc-4.0`**; Kaggle API: **CC BY 4.0**. The two hosts disagree; use the stricter (NC) **[practice]** | `load_dataset("Tobi-Bueck/customer-support-tickets")` | **Medium for German style**, low for content: email-shaped German tickets with agent answers, mostly IT. The card advertises a "Synthetic IT Ticket Generator"; whether this dataset itself is synthetic is **[unverified]**. |
| [Skytrax reviews, efehandanisman (Kaggle)](https://www.kaggle.com/datasets/efehandanisman/skytrax-airline-reviews) | ~24 MB, English, 2006–2019 | `airline, overall, author, review_date, customer_review, aircraft, traveller_type, cabin, date_flown, seat_comfort, cabin_service, food_bev, entertainment, ground_service, value_for_money, recommended` (Kaggle description) | Uploader states **CC0**; content was scraped from airlinequality.com, so the uploader's licence does not settle the reviewers'/site's rights **[practice]** | `kaggle datasets download efehandanisman/skytrax-airline-reviews` | **Medium-low.** Long narrative texts with real disruption stories; ratings, not complaint labels. Whether Condor reviews are included is **[unverified]**. |
| [128k Airline Reviews, joelljungstrom (Kaggle)](https://www.kaggle.com/datasets/joelljungstrom/128k-airline-reviews) | ~44 MB, English, 2001–2023, scraped from airlinequality.com | Review text + rating dimensions (Kaggle description) | Uploader states ODbL (Database) / Database Contents; same scraping caveat | `kaggle datasets download joelljungstrom/128k-airline-reviews` | **Medium-low.** Largest review corpus; can be filtered by airline to find leisure-carrier disruption stories. |
| [CFPB consumer complaints (HF)](https://huggingface.co/datasets/CFPB/consumer-finance-complaints) | millions of rows, English | Product/issue labels + narratives | HF tag `cc0-1.0` | `load_dataset("CFPB/consumer-finance-complaints")` | **Low.** Finance only; only useful as a template for a "complaint + label + company response" schema. |
| [US DOT Air Travel Consumer Report](https://www.transportation.gov/individuals/aviation-consumer-protection/air-travel-consumer-reports) | Monthly PDF reports | Complaint **counts** per airline and category (flight problems, baggage, refunds, customer service, oversales, ...); no complaint text ([2026 reports](https://www.transportation.gov/resources/individuals/aviation-consumer-protection/air-travel-consumer-reports-2026)) | US federal publication (public domain status **[unverified]**) | PDF download | **Low.** Only for category distributions; transportation.gov returned 403 to direct fetches. |
| [τ²-bench airline domain (GitHub, Sierra)](https://github.com/sierra-research/tau2-bench) | `data/tau2/domains/airline/`: `policy.md`, `db.json`, `tasks.json` | Agent policy (book/modify/cancel, "refunds and compensation"), a mock reservation DB and graded tasks ([policy.md](https://raw.githubusercontent.com/sierra-research/tau2-bench/main/data/tau2/domains/airline/policy.md)) | **MIT** (GitHub API) | `git clone` | **Medium as a pattern**, not as data: shows how to pair a written company policy, a mock DB and tasks with expected end state. US-style fictional policy, no EU261. |
| [EU Air Passenger Rights Instruction Dataset (HF, kenax69)](https://huggingface.co/datasets/kenax69/EU-Air-Passenger-Rights-Instruction-Dataset-AAA) | 1,161 conversations, **French** | ShareGPT `conversations` Q&A on Reg. 261/2004 and CJEU case law | Card: `mit` | `load_dataset(...)` | **Low.** Legal Q&A, not complaints; quality unaudited **[unverified]**; marketing-heavy card. |

Not found: a public German airline-complaint email corpus, a public EU261 claim dataset with
outcomes, and a Bitext airline-specific dataset (the [Bitext HF organisation](https://huggingface.co/bitext)
lists travel, hospitality, events-ticketing and others, but no airline set).

---

## 2. Ground truth / reference data (short)

| Source | Use | Notes |
|---|---|---|
| [OurAirports data](https://ourairports.com/data/) | Airport coordinates for the great-circle distance that Art. 7(4) Reg. 261/2004 prescribes | `airports.csv` columns include `latitude_deg, longitude_deg, iso_country, icao_code, iata_code` ([raw CSV on GitHub](https://github.com/davidmegginson/ourairports-data)); "All data is released to the Public Domain"; updated nightly. Filter on `type` in (`large_airport`, `medium_airport`) because IATA-like codes collide in `local_code` (e.g. a small Argentine strip with local code FRA). |
| [BTS Reporting Carrier On-Time Performance](https://www.transtats.bts.gov/DL_SelectFields.aspx?gnoyr_VQ=FGJ&QO_fu146_anzr=b0-gvzr) | Realistic per-flight delay/cancellation distributions | 1987–present (latest Aug 2026), fields incl. `Distance` (miles), `ArrDelay` (min), `Cancelled`, `CancellationCode`, `Origin`, `Dest`. US domestic only, so EU261 does not apply to these flights. |
| Public per-flight EU delay data | — | None verified. **[practice]** Generate a mock Condor flight table (flight no., date, origin, destination, scheduled/actual times, cancellation flag, notice date, cause code) and derive the complaint texts from it, so the pipeline's lookup and the expected outcome share one source of truth. |

Worked distances (haversine, R = 6371.0088 km, OurAirports coordinates): FRA–PMI 1,251 km
(EUR 250 tier); FRA–HRG 3,324 km, a non-intra-EU flight between 1,500 and 3,500 km (EUR 400 tier).

---

## 3. Legal framework

### 3.1 Regulation (EC) No 261/2004 (in force today)

Source text: [CELEX 32004R0261 on EUR-Lex](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32004R0261),
OJ L 46, 17.2.2004, p. 1. EUR-Lex itself serves a bot challenge to scripts; the same text is
machine-readable through the Publications Office Cellar:
`curl -L -H "Accept: text/html" -H "Accept-Language: eng" https://publications.europa.eu/resource/celex/32004R0261`
(XHTML/Formex variants via `Accept: application/xhtml+xml`). The statements below were checked
against that text.

| Article | Content |
|---|---|
| Art. 3 Scope | Departures from an EU airport; arrivals in the EU from a third country **only if the operating carrier is a Community carrier** (Condor is). Passenger needs a confirmed reservation and check-in at the stated time or, if none, "not later than 45 minutes before the published departure time". Not for free / non-public reduced fares; frequent-flyer tickets are covered. |
| Art. 4 Denied boarding | Call for volunteers first; if boarding is denied against the passenger's will, "immediately compensate them in accordance with Article 7 and assist them in accordance with Articles 8 and 9". |
| Art. 5 Cancellation | Right to Art. 8 (refund/rerouting) and Art. 9 care; compensation under Art. 7 **unless** informed (i) ≥ 2 weeks before departure, or (ii) 2 weeks–7 days before and rerouted to depart ≤ 2 h earlier and arrive < 4 h later, or (iii) < 7 days before and rerouted to depart ≤ 1 h earlier and arrive < 2 h later. Art. 5(3): no compensation if caused by "extraordinary circumstances which could not have been avoided even if all reasonable measures had been taken". Art. 5(4): burden of proof for notice lies with the carrier. |
| Art. 6 Delay | Care when departure delay is ≥ 2 h (≤ 1,500 km), ≥ 3 h (intra-EU > 1,500 km and other 1,500–3,500 km), ≥ 4 h (all others); hotel + transfer if the new departure is the next day; at ≥ 5 h the Art. 8(1)(a) refund option. The text grants **no compensation for delay**; see Sturgeon below. |
| Art. 7 Compensation | EUR 250 (≤ 1,500 km), EUR 400 (intra-EU > 1,500 km and other 1,500–3,500 km), EUR 600 (all others). Art. 7(2): may be reduced by 50 % if rerouting arrives within 2/3/4 h of scheduled arrival for the respective band. Art. 7(3): cash/bank transfer/cheque, vouchers only with signed agreement. Art. 7(4): great-circle distance. |
| Art. 8 Reimbursement / re-routing | Choice between refund "within seven days" of the full ticket price (plus return flight to origin when relevant), rerouting at the earliest opportunity, or rerouting at a later date. |
| Art. 9 Care | Meals and refreshments "in a reasonable relation to the waiting time", hotel when a stay becomes necessary, transfer, two calls/e-mails. |
| Art. 10 Downgrading | Refund within 7 days of 30 % (≤ 1,500 km), 50 % (intra-EU > 1,500 km and other 1,500–3,500 km), 75 % (others) of the ticket price. |
| Art. 15 / 16 | Rights cannot be waived; each Member State designates an enforcement body, to which passengers may complain. |

**Sturgeon (delay compensation).** CJEU, joined cases **C-402/07 and C-432/07**, *Sturgeon and
Others v Condor Flugdienst GmbH* and *Böck and Lepuschitz v Air France*, judgment of 19 November
2009 ([EUR-Lex CELEX 62007CJ0402](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:62007CJ0402);
[curia case file](https://curia.europa.eu/juris/liste.jsf?num=C-402/07)). Operative part, point 2:
delayed passengers "may rely on the right to compensation laid down in Article 7 ... where they
reach their final destination three hours or more after the arrival time originally scheduled",
unless the carrier proves extraordinary circumstances. Point 3: a technical problem is not an
extraordinary circumstance unless it stems from events "not inherent in the normal exercise of
the activity of the air carrier". The defendant in the German reference was Condor itself.

### 3.2 Revision: Regulation (EU) 2026/2202 (adopted, applies from 23 October 2027)

- Procedure: Conciliation Committee joint text of 15 June 2026; Parliament approval 7 July 2026;
  Council final approval 13 July 2026 ([Council press release](https://www.consilium.europa.eu/en/press/press-releases/2026/07/13/council-gives-final-clearance-for-stronger-air-passenger-rights/), not fetchable: 403; date from search listing).
- Published as **Regulation (EU) 2026/2202** of 16 September 2026, OJ L series 2.10.2026
  ([EUR-Lex ELI](https://eur-lex.europa.eu/eli/reg/2026/2202/oj/eng); text read via Cellar
  `celex/32026R2202`, `Accept: application/xhtml+xml`). It amends 261/2004 and 2027/97.
- Final article: enters into force on the 20th day after publication; "It shall apply from
  **23 October 2027**." So for all disruptions in the hackathon timeframe the 2004 text plus
  case law applies.
- Points read in the amending text (useful for a "future rules" toggle):
  - New Art. 6(4): compensation "when they reach their final destination with a delay at arrival
    exceeding three hours" (codifies Sturgeon). New Art. 6(3): refund offer at 5 h departure delay.
  - New Art. 7(1): amounts stay EUR 250 / 400 / 600, now per *journey*; Art. 7(5): distance from
    initial departure to final destination, great-circle.
  - New Art. 7(2): 50 % reduction only for the EUR 600 band, if arrival is ≤ 4 h late.
  - New Art. 7(4): carrier must send compensation information "within 96 hours of the
    termination of the journey". Art. 7(9): passenger request within **nine months**; carrier
    acknowledges immediately and pays or justifies refusal within **30 calendar days**, naming
    the extraordinary circumstance from the new Annex.
  - New Art. 6a tarmac delay (disembark at 2 h), Art. 6b missed connections, Art. 15a complaint
    handling: complaint within 12 months (or 3 months after the compensation request),
    acknowledgement within 7 working days, reasoned reply within one month (max. two months).

### 3.3 Montreal Convention 1999 and Regulation (EC) 2027/97 / 889/2002 (baggage)

Convention text as published in the OJ: [CELEX 22001A0718(01)](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:22001A0718(01)) (read via Cellar).

- **Art. 17(2)**: carrier liable for destruction, loss or damage of checked baggage if the event
  occurred on board or while the baggage was in its charge, except inherent defect; unchecked
  baggage only on fault. **Art. 17(3)**: baggage not arrived "at the expiration of 21 days" can be
  treated as lost.
- **Art. 19**: liability for delay of passengers and baggage unless all reasonable measures were taken.
- **Art. 22(2)**: baggage liability limited per passenger (original 1,000 SDR) unless a special
  declaration of interest was made.
- **Art. 31(2)–(4)**: complaint "forthwith after the discovery of the damage, and, at the latest,
  within **seven days** from the date of receipt" for checked baggage; for delay "within
  **21 days** from the date on which the baggage ... have been placed at his or her disposal";
  in writing; no action otherwise, save fraud.
- **Art. 35**: action within two years from arrival.
- **Current limits** (ICAO Art. 24 review, effective **28 December 2024**,
  [ICAO notice](https://www.icao.int/sites/default/files/secretariat/legal/LEB%20Treaty%20Collection%20Documents/2024_Revised_Limits_of_Liability_Under_the_Montreal_Convention_of_1999_en.pdf)):
  Art. 21: 151,880 SDR; Art. 22(1) passenger delay: 6,303 SDR; **Art. 22(2) baggage: 1,519 SDR**;
  Art. 22(3) cargo: 26 SDR/kg.
- **Reg. (EC) 2027/97 as amended by 889/2002** ([CELEX 32002R0889](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32002R0889)):
  Community carriers' liability is "governed by all provisions of the Montreal Convention", extended
  to domestic flights; its Annex is the passenger notice repeating the 7-day / 21-day written
  complaint rule (the Annex still quotes the original 1,000 / 4,150 SDR figures).

### 3.4 German context

- **Out-of-court dispute resolution, LuftVG §§ 57–57b**
  ([§ 57](https://www.gesetze-im-internet.de/luftvg/__57.html), [§ 57a](https://www.gesetze-im-internet.de/luftvg/__57a.html),
  [§ 57b](https://www.gesetze-im-internet.de/luftvg/__57b.html)): § 57 private conciliation bodies
  recognised by the Federal Ministry of Justice; § 57a official conciliation at the Bundesamt für
  Justiz for carriers that do not take part in a private one; § 57b(1) covers consumer payment
  claims up to EUR 5,000 for denied boarding, delay, downgrade, cancellation, baggage, items carried,
  and PRM duties. § 57b(2) No. 6: not admissible if the claim was not first raised with the
  airline, unless the airline rejected it or has not decided within **2 months**; No. 7: not for
  claims ≤ EUR 10.
- **söp is now "Schlichtungsstelle Reise & Verkehr e.V."** (site says "ehemals söp",
  [schlichtung-reise-und-verkehr.de](https://schlichtung-reise-und-verkehr.de/)), free of charge
  for consumers. Condor names it as its conciliation body (Condor AGB § 22.3, see 4.1;
  [Condor arbitration page](https://www.condor.com/eu/help-contact/arbitration-board.jsp):
  claim between EUR 10 and EUR 30,000; Condor first, then after 2 months or a rejection).
- **Luftfahrt-Bundesamt (LBA)** is the "Nationale Durchsetzungs- und Beschwerdestelle
  Fluggastrechte" ([LBA Z5](https://www.lba.de/DE/LBA/Organisation/Abteilung_Z/Z5/Z5_node.html),
  [complaint forms](https://www.lba.de/DE/Fluggastrechte/Beschwerdeformulare/Beschwerdeformulare_node.html)).
  It pursues violations under administrative-offence law but does not enforce individual civil
  claims; it refers passengers to conciliation or the courts
  ([LBA Schlichtung](https://www.lba.de/DE/Fluggastrechte/Schlichtung/Schlichtung_node.html);
  wording taken from search snippets, page not fetched: **[unverified]**).

---

## 4. Condor company processes

Fetching notes: `curl` against condor.com returns 403 (bot protection); WebFetch worked for
individual pages and the AGB PDF. `support-de.condor.com` (FAQ) did not resolve at research time,
so FAQ statements below that come only from search snippets are marked **[unverified]**.

### 4.1 Conditions of carriage: Condor AGB, Stand 23 September 2026

[Allgemeine Geschäfts- und Beförderungsbedingungen der Condor Flugdienst GmbH (PDF, 48 pages)](https://www.condor.com/de/fileadmin/dam/agb/de/agb.pdf).
The document titled "Allgemeine Beförderungsbedingungen" (ABB) on condor.com is for **cargo** only
([ABB Fracht](https://www.condor.com/de/fileadmin/dam/pdf/ABB-Fracht_Deutsch_September-2025.pdf)).
English US/Canada version: [GTBC June 2025](https://www.condor.com/us/fileadmin/dam/pdf/AGB/AGB_Englisch_CA_Juni_2025.pdf).

- **§ 16.1.2**: Montreal limits quoted with the 2024 values: 151,880 SDR, baggage **1,519 SDR
  ("rund 1.800 Euro")**, passenger delay 6,303 SDR. (The baggage web page says "etwa 1.900,00 €";
  the EUR figure depends on the SDR rate.)
- **§ 16.2.1**: damage/loss must be reported at the airport, where a **PIR** (Property Irregularity
  Report) is issued; accepting baggage without a PIR creates a presumption of undamaged delivery;
  scratches and small dents are wear, not damage.
- **§ 16.2.2**: written notice "unverzüglich, jedoch spätestens binnen 7 Tagen", for delayed
  baggage "binnen 21 Tagen"; the date of sending counts; "Die Aushändigung eines PIR wahrt nicht
  die oben genannten Fristen" (a PIR alone does not meet the deadline).
- **§ 16.3**: two-year limitation period.
- **§ 17.1–17.4**: schedule changes for extraordinary circumstances or operational reasons
  (notified ≥ 2 weeks in advance); Condor lists examples (weather, strikes, ATC decisions, security).
- **§ 17.5**: notice on Reg. 261/2004 (care thresholds 2/3/4 h, refund within 7 days at > 5 h delay,
  denied boarding compensation by distance).
- **§ 22.3**: "Condor nimmt an einem Streitbeilegungsverfahren vor einer
  Verbraucherschlichtungsstelle teil" – Schlichtungsstelle Reise & Verkehr e.V., Fasanenstraße 81,
  10623 Berlin. § 22.4: German version prevails.

### 4.2 EU261 compensation claim

[Formular Entschädigungsanspruch](https://www.condor.com/de/hilfe-kontakt/kontakt/beschwerdeformular-eu261.jsp)
([EN](https://www.condor.com/eu/help-contact/contact/complaint-form-eu261.jsp)):
1. Scope stated on the page: cancellation, delay over three hours, overbooking; flights departing
   EU airports and EU carriers landing in the EU.
2. Enter flight data and passenger names "wie auf der Buchungsbestätigung Ihrer ursprünglichen
   Buchung angegeben"; mandatory fields marked `*` (field list not visible to the fetcher).
3. Group bookings: claim only for passengers you may represent; attach a signed
   Vollmachtserklärung (PDF linked on the page) for third parties.
4. Condor replies whether there is an entitlement; no response time stated.

### 4.3 General complaints and feedback

[Kundenservice page](https://www.condor.com/de-de/informationen-services/hilfe-kontakt/kundenservice/):
contact form where the user "zunächst eine Kategorie und ein Thema" selects (category list not
visible to the fetcher); hotline +49 (0) 6171 69889 88 and WhatsApp +49 (0) 6171 69889 16, 24 h,
German or English; no response time ("so bald wie möglich"). Per Condor FAQ snippets: booking
number required; bookings via third parties/tour operators are handled by the seller; postal
route to Customer Relations **[unverified]**.

### 4.4 Baggage

[Verlorenes, verspätetes, beschädigtes Gepäck](https://www.condor.com/de-de/informationen-services/gepaeck/verlorenes-verspaetetes-beschaedigtes-gepaeck/):

| Case | Steps on the page |
|---|---|
| Delayed | Status in the **mybag.aero** self-service (reference number + surname). Days 1–5: local handling partner searches. After 5 days: fill in a detailed contents list; extended search (Fraport) up to 3 weeks. After **21 days** baggage counts as lost, file goes to customer service, compensation under Montreal. Interim purchases: online cost-refund form **within 21 days** of receiving the bag, with receipts; purchases at the home location are not refunded. |
| Damaged | Report via mybag.aero or at the Condor Lost & Found counter **before leaving the airport**; self-service only within **72 hours** after the flight. Claim within **7 days** of receipt, via a service provider (Dolfi 1920 GmbH, typically 14 working days), travel insurance, or Condor customer service. |
| Missing contents / damaged mobility aids | Contact Condor customer service immediately, at the latest within 7 days. |
| Items left on board | PDF search request form; lost-and-found at the arrival airport, usually kept up to four weeks. |
| Exclusions | Page lists no liability for valuables, cash, medication, fragile/perishable items. |

### 4.5 Refunds

No dedicated refund-process page was found. Sources: Reg. 261/2004 Art. 8 (refund within 7 days
on cancellation or ≥ 5 h delay), AGB § 17.5.3, and the EU261 form page (which says Condor will
tell the passenger whether a "Rückerstattung" is due). Fare-dependent refunds after a
passenger-initiated cancellation are in AGB § 7 (not analysed in detail) **[unverified]**.

---

## 5. Recommendation

### 5.1 Datasets to use

1. **Twitter US Airline Sentiment** (CC BY-NC-SA 4.0) as the *real-text* seed: take the
   `negative` tweets with `negativereason` in {Late Flight, Cancelled Flight, Lost Luggage,
   Damaged Luggage, Customer Service Issue, Flight Booking Problems} as style and topic seeds.
   Fine for a non-commercial hackathon demo; do not ship it in a product **[practice]**.
2. **Tobi-Bueck customer-support-tickets** (treat as CC BY-NC 4.0) as the *German email style*
   seed: use the `de` rows (subject/body/answer) as few-shot examples of German customer-email
   register and agent replies.

Bitext travel (CDLA-Sharing-1.0) is a good optional addition if the pipeline has an intent router.

### 5.2 Plan for a synthetic Condor test set **[practice]**

1. **Build the facts first.** Generate 100–300 mock flights on real Condor-type leisure routes
   (FRA/MUC/DUS ↔ PMI, HRG, AYT, LPA, JFK ...) with scheduled/actual times, cancellation flag,
   notice date, rerouting offer and a cause code (technical, weather, strike-ATC, crew). Compute
   distance from OurAirports with haversine.
2. **Compute the expected outcome deterministically** with a small rules function implementing
   Art. 5/6/7/8/9/10 of 261/2004 + Sturgeon + Montreal Art. 22/31 + Condor AGB deadlines. This is
   the oracle; the LLM never decides the label.
3. **Generate the complaint text with an LLM** from (facts + persona + channel + language +
   style seed sampled from the Twitter or Tobi-Bueck rows). Vary: German/English, email vs.
   web-form vs. short social post, missing booking number, wrong dates, angry tone, mixed claims
   (delay + lost baggage), claims by a third party, tour-operator bookings, late baggage notice
   (day 9), extraordinary circumstances (storm, ATC strike), cancellation notified 10 days ahead
   with acceptable rerouting, downgrade.
4. **Include negative and edge cases** on purpose: 2h55 arrival delay (no compensation), departure
   from a non-EU airport on a non-EU carrier, technical defect (compensation due per Sturgeon
   point 3), damage reported after 7 days, claim already rejected > 2 months ago (route to
   Schlichtungsstelle Reise & Verkehr).
5. **Validate** a 10 % sample by hand against the legal table in section 3, and keep the generator
   prompt, seed IDs and rules version in each record for reproducibility.

### 5.3 Proposed test-case JSON schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "CondorComplaintTestCase",
  "type": "object",
  "required": ["case_id", "input", "facts", "expected"],
  "properties": {
    "case_id": { "type": "string", "pattern": "^TC-[0-9]{4}$" },
    "input": {
      "type": "object",
      "required": ["channel", "language", "text"],
      "properties": {
        "channel": { "enum": ["email", "contact_form", "eu261_form", "social", "letter"] },
        "language": { "enum": ["de", "en"] },
        "subject": { "type": "string" },
        "text": { "type": "string" },
        "received_at": { "type": "string", "format": "date-time" },
        "attachments": { "type": "array", "items": { "enum": ["boarding_pass", "booking_confirmation", "pir", "receipts", "power_of_attorney", "photos"] } }
      }
    },
    "facts": {
      "type": "object",
      "required": ["booking_ref", "flight_no", "origin", "destination", "scheduled_departure", "scheduled_arrival"],
      "properties": {
        "booking_ref": { "type": ["string", "null"] },
        "booked_via": { "enum": ["condor_direct", "travel_agent", "tour_operator", "ota"] },
        "passengers": { "type": "integer", "minimum": 1 },
        "flight_no": { "type": "string" },
        "origin": { "type": "string", "description": "IATA" },
        "destination": { "type": "string", "description": "IATA" },
        "distance_km": { "type": "number" },
        "scheduled_departure": { "type": "string", "format": "date-time" },
        "scheduled_arrival": { "type": "string", "format": "date-time" },
        "actual_arrival": { "type": ["string", "null"], "format": "date-time" },
        "cancelled": { "type": "boolean" },
        "cancellation_notice_days": { "type": ["integer", "null"] },
        "rerouting_offered": { "type": ["object", "null"] },
        "denied_boarding": { "type": "boolean" },
        "downgrade": { "type": ["object", "null"], "properties": { "booked_class": { "type": "string" }, "flown_class": { "type": "string" }, "ticket_price_eur": { "type": "number" } } },
        "cause_code": { "enum": ["technical", "weather", "atc_strike", "airline_staff_strike", "crew_shortage", "security", "airport_closure", "none"] },
        "baggage": { "type": ["object", "null"], "properties": { "issue": { "enum": ["delayed", "lost", "damaged", "pilfered"] }, "pir_issued": { "type": "boolean" }, "bag_received_at": { "type": ["string", "null"], "format": "date-time" }, "claimed_amount_eur": { "type": "number" } } },
        "prior_contact": { "type": ["object", "null"], "properties": { "first_claim_at": { "type": "string", "format": "date" }, "airline_response": { "enum": ["none", "rejected", "partial", "accepted"] } } }
      }
    },
    "expected": {
      "type": "object",
      "required": ["claim_types", "applicable_law", "next_step"],
      "properties": {
        "claim_types": { "type": "array", "items": { "enum": ["delay", "cancellation", "denied_boarding", "downgrade", "baggage_delayed", "baggage_lost", "baggage_damaged", "refund", "care_costs", "service_feedback", "other"] } },
        "applicable_law": { "type": "array", "items": { "enum": ["EC261/2004", "CJEU_C-402/07", "MC99_Art17", "MC99_Art19", "MC99_Art22", "MC99_Art31", "EC2027/97", "LuftVG_57b", "Condor_AGB_16", "Condor_AGB_17", "none"] } },
        "eu261_compensation_eur": { "type": ["integer", "null"], "enum": [0, 125, 200, 250, 300, 400, 600, null] },
        "refund_due": { "type": "boolean" },
        "downgrade_refund_pct": { "type": ["integer", "null"], "enum": [30, 50, 75, null] },
        "baggage_limit_sdr": { "type": ["integer", "null"] },
        "deadline_missed": { "type": "boolean" },
        "extraordinary_circumstances": { "type": "boolean" },
        "next_step": { "enum": ["pay_compensation", "request_missing_info", "redirect_to_tour_operator", "redirect_to_eu261_form", "open_baggage_claim_mybag", "forward_to_dolfi1920", "reject_with_reason", "refer_to_schlichtungsstelle", "escalate_human"] },
        "missing_info": { "type": "array", "items": { "type": "string" } },
        "rationale": { "type": "string" }
      }
    },
    "provenance": {
      "type": "object",
      "properties": { "seed_dataset": { "type": "string" }, "seed_id": { "type": "string" }, "generator_model": { "type": "string" }, "rules_version": { "type": "string" } }
    }
  }
}
```

The `eu261_compensation_eur` enum includes the 50 % reductions under Art. 7(2) (125, 200, 300).
