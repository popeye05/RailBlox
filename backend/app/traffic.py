"""Read-only movement enquiries over immutable planning snapshots, never live telemetry."""
import csv
import io
from datetime import datetime, timedelta
from typing import Literal
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from .adapters import safe_csv


def movement_enquiry(snapshot, start, end, search='', direction='', kind='', origin='', destination=''):
    sections = {section['id']: section for section in snapshot.sections}
    stations = {station for section in snapshot.sections for station in (section['origin'], section['destination'])}
    if end <= start:
        raise HTTPException(422, 'End time must be after start time.')
    if (origin and origin not in stations) or (destination and destination not in stations):
        raise HTTPException(422, 'Choose stations from this corridor.')
    if origin and origin == destination:
        raise HTTPException(422, 'Origin and destination must be different stations.')
    records = []
    for movement in snapshot.movements:
        if search.casefold() not in movement['id'].casefold():
            continue
        if direction and movement.get('direction') != direction:
            continue
        if kind and movement.get('kind') != kind:
            continue
        route = []
        for entry in sorted(movement['occupancies'], key=lambda item: (item['start'], item['end'])):
            section = sections[entry['section']]
            # Snapshot endpoints follow increasing chainage on both lines. DOWN
            # traverses those endpoints in reverse; do not rewrite source data.
            endpoints = (section['destination'], section['origin']) if section.get('line') == 'DN' else (section['origin'], section['destination'])
            route.append({**entry, 'origin': endpoints[0], 'destination': endpoints[1]})
        # Match an ordered, connected station-to-station leg, not an unordered pair.
        if origin or destination:
            legs = []
            for i, entry in enumerate(route):
                if origin and entry['origin'] != origin:
                    continue
                for j in range(i, len(route)):
                    if j > i and (route[j-1]['destination'] != route[j]['origin']
                                  or route[j]['start'] < route[j-1]['end']):
                        break
                    if not destination or route[j]['destination'] == destination:
                        legs = route[i:j+1] if destination else route[i:]
                        break
                if legs:
                    break
            route = legs
        visible = [entry for entry in route if entry['start'] < end and entry['end'] > start]
        if not visible:
            continue
        records.append({
            'id': movement['id'], 'kind': movement.get('kind', 'Unknown'),
            'direction': movement.get('direction', 'Unknown'),
            'forecast_at': movement.get('forecast'), 'margin': movement.get('margin', 0),
            'occupancies': visible,
            'first_entry': min(entry['start'] for entry in visible),
            'last_exit': max(entry['end'] for entry in visible),
            'section_minutes': sum(min(end, entry['end']) - max(start, entry['start']) for entry in visible),
        })
    records.sort(key=lambda record: (record['first_entry'], record['id']))
    return {'snapshot_id': snapshot.id, 'anchor': snapshot.anchor, 'start': start, 'end': end,
            'records': records, 'count': len(records),
            'section_minutes': sum(record['section_minutes'] for record in records),
            'basis': 'Saved section occupancy estimates; not actual train running or a live control chart.'}


def traffic_router(store):
    router = APIRouter(prefix='/api/traffic', tags=['Train enquiry'])

    def enquiry(snapshot_id: str, start: int = Query(0, ge=0, le=44639),
                end: int = Query(1440, ge=1, le=44640), search: str = Query('', max_length=100),
                direction: Literal['', 'UP', 'DN'] = '', kind: str = Query('', max_length=40),
                origin: str = Query('', max_length=100), destination: str = Query('', max_length=100)):
        return movement_enquiry(store.snapshot(snapshot_id), start, end, search, direction, kind, origin, destination)

    router.add_api_route('/movements', enquiry, methods=['GET'])

    @router.get('/movements/export')
    def export(snapshot_id: str, start: int = Query(0, ge=0, le=44639),
               end: int = Query(1440, ge=1, le=44640), search: str = Query('', max_length=100),
               direction: Literal['', 'UP', 'DN'] = '', kind: str = Query('', max_length=40),
               origin: str = Query('', max_length=100), destination: str = Query('', max_length=100)):
        data = enquiry(snapshot_id, start, end, search, direction, kind, origin, destination)
        stream = io.StringIO(newline='')
        writer = csv.writer(stream)
        columns = ['Snapshot', 'Train', 'Category', 'Direction', 'Section', 'Origin', 'Destination',
                   'Entry ISO', 'Exit ISO', 'Minutes in selected interval', 'Basis']
        writer.writerow(columns)
        rows = []
        anchor = datetime.fromisoformat(data['anchor'])
        for record in data['records']:
            for entry in record['occupancies']:
                rows.append(dict(zip(columns, [snapshot_id, record['id'], record['kind'], record['direction'],
                    entry['section'], entry['origin'], entry['destination'],
                    (anchor + timedelta(minutes=entry['start'])).isoformat(),
                    (anchor + timedelta(minutes=entry['end'])).isoformat(),
                    min(end, entry['end']) - max(start, entry['start']), 'Saved occupancy estimate'])))
        return Response('\ufeff' + (safe_csv(rows) if rows else stream.getvalue()), media_type='text/csv',
                        headers={'Content-Disposition': 'attachment; filename="railblox-train-enquiry.csv"'})

    return router
