import csv
import io
import pytest
from fastapi import HTTPException
from app.fixtures import acceptance
from app.permissions import required_role, capabilities, PUBLIC_AUTH_ROUTES
from app.traffic import movement_enquiry
from test_platform import secure, bearer


def test_movement_enquiry_ordered_stations_and_interval_overlap():
    snapshot = acceptance()
    outbound = snapshot.movements[0]['occupancies']
    sections = {section['id']: section for section in snapshot.sections}
    origin = sections[outbound[0]['section']]['origin']
    destination = sections[outbound[-1]['section']]['destination']
    result = movement_enquiry(snapshot, 95, 115, direction='UP', origin=origin, destination=destination)
    assert result['count'] == 1
    assert result['records'][0]['id'] == 'FRT-01'
    assert result['section_minutes'] == 15  # 95..105 plus 110..115, not full-run duration.
    assert len(result['records'][0]['occupancies']) == 2
    assert movement_enquiry(snapshot, 0, 1440, direction='UP', origin=destination, destination=origin)['count'] == 0
    assert movement_enquiry(snapshot, 105, 110, direction='UP')['count'] == 0  # half-open intervals
    assert movement_enquiry(snapshot, 0, 1440, search='pax', kind='Passenger')['count'] == 1
    down = movement_enquiry(snapshot, 0, 1440, direction='DN', origin=destination, destination=origin)
    assert down['count'] == 1
    assert down['records'][0]['occupancies'][0]['origin'] == destination
    assert down['records'][0]['occupancies'][-1]['destination'] == origin
    assert movement_enquiry(snapshot, 0, 1440, direction='DN', origin=origin, destination=destination)['count'] == 0
    with pytest.raises(HTTPException):
        movement_enquiry(snapshot, 10, 9)
    with pytest.raises(HTTPException):
        movement_enquiry(snapshot, 0, 10, origin='UNKNOWN')


def test_station_enquiry_does_not_join_disconnected_legs():
    snapshot = acceptance()
    movement = snapshot.movements[0]
    movement['occupancies'] = [movement['occupancies'][0], movement['occupancies'][2]]
    sections = {section['id']: section for section in snapshot.sections}
    assert movement_enquiry(snapshot, 0, 1440, direction='UP',
        origin=sections['S1-UP']['origin'], destination=sections['S3-UP']['destination'])['count'] == 0


def test_all_four_roles_can_query_and_export_but_only_own_activity(secure):
    store = secure.app.state.store
    from app.security import principal
    for role in ['viewer', 'planner', 'officer', 'admin']:
        token = principal.set({'id': role, 'role': role, 'division': 'division-a'})
        store.audit('test-recorded', 'record-'+role, {})
        principal.reset(token)
    for role in ['viewer', 'planner', 'officer', 'admin']:
        headers = bearer(role)
        assert secure.get('/api/traffic/movements?snapshot_id=small-v1', headers=headers).json()['count'] == 2
        response = secure.get('/api/traffic/movements/export?snapshot_id=small-v1&search=FRT&start=95&end=115', headers=headers)
        assert response.status_code == 200
        rows = list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig'))))
        assert len(rows) == 2
        assert sum(int(row['Minutes in selected interval']) for row in rows) == 15
        activity = secure.get('/api/auth/activity', headers=headers).json()
        assert [row['record_id'] for row in activity] == ['record-'+role]
        assert 'data' not in activity[0]
        permissions = secure.get('/api/auth/permissions', headers=headers).json()
        assert permissions['granted'] == capabilities(role)
    assert secure.get('/api/traffic/movements?snapshot_id=small-v1').status_code == 401
    assert secure.get('/api/traffic/movements?snapshot_id=small-v1&start=-1', headers=bearer('viewer')).status_code == 422
    assert secure.get('/api/traffic/movements?snapshot_id=small-v1&end=50000', headers=bearer('viewer')).status_code == 422


def test_csv_export_neutralizes_formula_in_source_identifiers(secure):
    snapshot = acceptance().model_copy(deep=True)
    snapshot.id = 'formula-export'
    snapshot.movements[0]['id'] = '=HYPERLINK("unsafe")'
    secure.app.state.store.save_snapshot(snapshot)
    response = secure.get('/api/traffic/movements/export?snapshot_id=formula-export&direction=UP', headers=bearer('viewer'))
    rows = list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig'))))
    assert rows[0]['Train'].startswith("'=HYPERLINK")


def test_every_write_route_declares_access_and_unknown_writes_fail_closed(secure):
    for path, operations in secure.app.openapi()['paths'].items():
        for method in set(operations) & {'post', 'patch', 'put', 'delete'}:
            required = required_role(method.upper(), path)
            if (method.upper(), path) in PUBLIC_AUTH_ROUTES:
                assert path == '/api/auth/username-login'
                continue
            assert required is not None, (method, path)
            for role in ['viewer', 'planner', 'officer', 'admin']:
                response = secure.request(method, path, headers=bearer(role), json={})
                levels = ['viewer', 'planner', 'officer', 'admin']
                if levels.index(role) < levels.index(required):
                    assert response.status_code == 403, (role, method, path)
    for role in ['viewer', 'planner', 'officer', 'admin']:
        assert secure.post('/api/unclassified-write', headers=bearer(role)).status_code == 403


def test_preflight_reports_configuration_without_credentials(monkeypatch):
    import json
    from app.preflight import check
    assert not check()['ready']
    for name, value in {
        'APP_ENV': 'production', 'AUTH_MODE': 'supabase',
        'SUPABASE_URL': 'https://identity.example.supabase.co',
        'SUPABASE_PUBLISHABLE_KEY': 'sb_publishable_valid_test',
        'SUPABASE_SERVICE_ROLE_KEY': 'server-secret-never-print-this',
        'DEPLOYMENT_DIVISION': 'division-a', 'CORS_ORIGINS': 'https://app.example.test',
        'DATABASE_URL': 'postgresql+psycopg://test:private-password@db.example.test/db?sslmode=verify-full',
        'PUBLIC_SIGNUP_ENABLED': 'false', 'COLLECT_DATE_OF_BIRTH': 'false',
        'REQUIRE_MFA': 'true',
    }.items():
        monkeypatch.setenv(name, value)
    result = check()
    assert result['ready']
    assert 'server-secret' not in json.dumps(result) and 'private-password' not in json.dumps(result)
    monkeypatch.setenv('REQUIRE_MFA', 'false')
    assert not check()['ready']
    monkeypatch.setenv('REQUIRE_MFA', 'true')
    monkeypatch.setenv('SUPABASE_PUBLISHABLE_KEY', 'sb_publishable_REPLACE_ME')
    assert not check()['ready']
