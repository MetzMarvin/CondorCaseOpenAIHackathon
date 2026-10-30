"""Small read-only Salesforce-shaped fixture adapter. No matching by name/email."""
from .contracts import Fact, SourceRef
from .preparation_contracts import LookupResult

CUSTOMERS = [{'id': '12345', 'name': 'Sophie Demo', 'email': 'sophie@example.com', 'language': 'en'}]
FLIGHTS = [dict(id=f'flight-{i}', flight_number='87B6', origin='FRA', destination='LHR',
                scheduled_departure=f'2026-10-{day}T08:00:00Z', scheduled_arrival=f'2026-10-{day}T09:30:00Z',
                actual_arrival=f'2026-10-{day}T09:30:00Z', cancelled=False, synthetic=True)
           for i, day in [(1, '28'), (2, '29')]]
BOOKINGS = [dict(id='booking-sophie', reference='SOPHIE1', contact_id='12345', flight_ids=['flight-1'], currency='EUR', synthetic=True)]


CUSTOMERS.append(dict(id='22222', name='Repeat Demo', email='repeat@example.com', language='en'))
BOOKINGS.extend([dict(id='repeat-'+str(i), reference='REPEAT'+str(i), contact_id='22222', flight_ids=['flight-'+str(i)], currency='EUR', synthetic=True) for i in (1,2)])


class SalesforceMock:
    def __init__(self, customers=None, bookings=None, flights=None):
        self.customers = CUSTOMERS if customers is None else customers
        self.bookings = BOOKINGS if bookings is None else bookings
        self.flights = FLIGHTS if flights is None else flights

    def lookup(self, facts):
        identifiers = {}
        for fact in facts:
            if fact.name in {'customer_id', 'booking_reference', 'flight_number', 'travel_date'}:
                identifiers.setdefault(fact.name, set()).add(str(fact.value).strip().upper())
        if any(len(values) > 1 for values in identifiers.values()):
            return LookupResult(status='AMBIGUOUS')
        keys = {name: next(iter(values)) for name, values in identifiers.items()}
        customer, reference, flight, date = (keys.get(k) for k in ('customer_id', 'booking_reference', 'flight_number', 'travel_date'))
        if not customer and not reference:
            return LookupResult(status='NOT_ATTEMPTED')
        customers = [c for c in self.customers if not customer or c['id'].upper() == customer]
        bookings = [b for b in self.bookings if b['contact_id'] in {c['id'] for c in customers}
                    and (not reference or b['reference'].upper() == reference)]
        pairs = [(b, f) for b in bookings for f in self.flights if f['id'] in b['flight_ids']
                 and (not flight or f['flight_number'].upper() == flight)
                 and (not date or f['scheduled_departure'][:10] == date)]
        def sourced(record):
            return tuple(Fact(name=k, value=v, sources=(SourceRef(source_id='salesforce:'+record['id'], version='1'),)) for k,v in record.items())
        if customer and not reference and not flight:
            return LookupResult(status='MATCHED', customer_context=sourced(customers[0])) if len(customers)==1 else LookupResult(status='NOT_FOUND')
        if len(pairs) != 1:
            return LookupResult(status='AMBIGUOUS' if pairs else 'NOT_FOUND')
        booking, flight_record = pairs[0]
        person = next(c for c in customers if c['id']==booking['contact_id'])
        return LookupResult(status='MATCHED', customer_context=sourced(person), booking_context=sourced(booking), flight_context=sourced(flight_record))
