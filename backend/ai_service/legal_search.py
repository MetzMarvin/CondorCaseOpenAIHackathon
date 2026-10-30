"""Research issue expansion. Search leads are not findings or applicability decisions."""
import re
from itertools import zip_longest

# Independent rights and defenses get their own retrieval slot. No payout labels.
FACETS = (
    (r'cancel|weather|storm', (
        'EU261 Article 5 cancellation notice extraordinary circumstances proof reasonable measures',
        'EU261 Article 9 right to care meals hotel accommodation transport extraordinary circumstances',
        'EU261 Article 8 choice reimbursement or re-routing accepted alternative flight',
        'EU261 Article 7 compensation distance reduction alternative flight arrival',
        'EU261 Article 3 scope confirmed reservation Community carrier departure',
    )),
    (r'\bflight.{0,35}(delay|late)|arriv.{0,25}late|missed.{0,15}connection', (
        'Sturgeon long delay arrival final destination three hours compensation',
        'EU261 Article 6 delay five hours reimbursement meals hotel assistance',
        'extraordinary circumstances burden proof reasonable measures flight delay',
        'connecting flights final destination single reservation missed connection scope',
    )),
    (r'bag|luggage|suitcase', (
        'Montreal Convention Article 19 delay baggage damage reasonable measures',
        'Montreal Convention Article 31 written complaint baggage delay twenty-one days disposal seven days damage',
        'Montreal Convention Article 22 baggage liability special declaration actual damage maximum not fixed rate',
        'Montreal Convention Article 24 revised liability limits baggage 2024 1519 SDR effective date',
        'Montreal Convention Article 17 checked baggage loss damage twenty-one days',
    )),
    (r'denied boarding|overbook|bumped|refused boarding', (
        'EU261 Article 4 denied boarding volunteers against their will compensation assistance',
        'EU261 Article 2 denied boarding reasonable grounds health safety security travel documentation',
        'EU261 Article 8 reimbursement re-routing denied boarding',
        'EU261 Article 9 right to care meals hotel accommodation transport',
    )),
    (r'wheelchair|disab|mobility|assistance dog', (
        'Regulation 1107/2006 Article 3 refusal carriage disability Article 4 safety exceptions reasons',
        'Regulation 1107/2006 Article 7 assistance airports no notification reasonable efforts',
        'Regulation 1107/2006 Article 8 Article 10 assistance without additional charge',
        'Regulation 1107/2006 Annex II mobility equipment assistance dogs seating',
    )),
    (r'downgrad|business.{0,20}economy', (
        'EU261 Article 10 downgrading reimbursement ticket price 30 50 75 percent',
    )),
    (r'injur|burn|accident', (
        'Montreal Convention Article 17 death bodily injury accident embarking disembarking',
        'Montreal Convention Article 21 compensation death injury defenses liability limits revision',
        'Montreal Convention Article 35 limitation actions two years',
    )),
)


def issue_queries(text):
    if not text.strip() or len(text) > 6000:
        raise ValueError('Provide case text of 1–6000 characters')
    groups = [queries for pattern, queries in FACETS if re.search(pattern, text, re.I)]
    # Interleave categories so a complaint about several problems retains each one.
    expanded = [q for row in zip_longest(*groups) for q in row if q]
    return list(dict.fromkeys([text, *expanded]))


def search_issues(rag, text, limit=20, per_query=5):
    """Round-robin unique passages; raw fusion scores are local to each query."""
    if not 1 <= limit <= 100 or not 1 <= per_query <= 100:
        raise ValueError('limits must be between 1 and 100')
    queries = issue_queries(text)
    lists = []
    for query in queries:
        # Explicitly named instruments should retrieve the instrument itself,
        # alongside commentary and judgments that quote the same vocabulary.
        primary = next((source for prefix, source in (
            ('EU261', 'eu261'), ('Montreal Convention', 'montreal-convention'),
            ('Regulation 1107/2006', 'accessibility'), ('Sturgeon', 'sturgeon'),
        ) if query.startswith(prefix)), None)
        general = rag.search(query, limit=per_query, kind='legal')
        direct = rag.search(query, limit=2, kind='legal', source_ids=(primary,)) if primary else []
        lists.append(direct + general)
    selected, seen = [], set()
    for row in zip_longest(*lists):
        for hit in row:
            if hit is None:
                continue
            key = (hit.chunk.source_id, hit.chunk.version, hit.chunk.chunk_id)
            if key not in seen:
                selected.append(hit)
                seen.add(key)
                if len(selected) == limit:
                    return selected
    return selected
