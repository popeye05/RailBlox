import json
from datetime import datetime, timedelta, timezone
import httpx
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.security import Settings
from app.learning import train
from test_api import wait


@pytest.fixture
def secure(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTH_MODE', 'supabase')
    monkeypatch.setenv('SUPABASE_URL', 'https://identity.example.supabase.co')
    monkeypatch.setenv('SUPABASE_PUBLISHABLE_KEY', 'sb_publishable_test')
    monkeypatch.setenv('DEPLOYMENT_DIVISION', 'division-a')
    async def get(self, url, headers):
        assert url == 'https://identity.example.supabase.co/auth/v1/user'
        token = headers['Authorization'][7:]
        if token == 'outage':
            raise httpx.ConnectError('private upstream information')
        if token == 'expired':
            return httpx.Response(401)
        return httpx.Response(200, json={'id': token, 'app_metadata': {
            'railblox_role': token if token in ('viewer', 'planner', 'officer', 'admin') else 'viewer',
            'railblox_division': 'wrong-division' if token == 'foreign' else 'division-a'},
            'user_metadata': {'railblox_role': 'admin'}})
    monkeypatch.setattr(httpx.AsyncClient, 'get', get)
    with TestClient(create_app('sqlite:///' + str(tmp_path/'secure.db'))) as client:
        yield client


def bearer(role):
    return {'Authorization': 'Bearer ' + role}


def test_every_data_route_requires_authentication(secure):
    for path in ['/api/context', '/api/snapshots/small-v1', '/api/intelligence/workspace?snapshot_id=small-v1',
                 '/api/samples/ROAMS', '/api/ai/history', '/api/admin/audit', '/api/plans']:
        assert secure.get(path).status_code == 401, path
    assert secure.get('/api/auth/config').json()['publishable_key'] == 'sb_publishable_test'
    assert secure.get('/health').status_code == 200
    assert secure.get('/api/context', headers=bearer('expired')).status_code == 401
    assert secure.get('/api/context', headers=bearer('foreign')).status_code == 403
    result = secure.get('/api/context', headers=bearer('outage'))
    assert result.status_code == 503 and 'private upstream' not in result.text


def test_readers_cannot_mutate_and_user_metadata_cannot_elevate(secure):
    for path, operations in secure.app.openapi()['paths'].items():
        if path.startswith('/api/'):
            for method in set(operations) & {'post', 'patch', 'delete', 'put'}:
                if path in {'/api/auth/username', '/api/auth/username-login'}:
                    continue  # Own-account alias and public password authentication; tested separately.
                result = secure.request(method, path, headers=bearer('viewer'), json={})
                assert result.status_code == 403, (method, path, result.text)
    assert secure.get('/api/auth/me', headers=bearer('viewer')).json()['role'] == 'viewer'
    for path in ['/api/plans/any/approve', '/api/plans/any/revise', '/api/intelligence/recommendations/any/decision',
                 '/api/intelligence/reports/any/review', '/api/intelligence/recommendations/any/outcomes']:
        assert secure.post(path, headers=bearer('planner'), json={}).status_code == 403
    assert secure.post('/api/admin/automation/run', headers=bearer('officer')).status_code == 403
    assert secure.get('/api/admin/audit', headers=bearer('viewer')).status_code == 403
    assert secure.get('/api/samples/ROAMS', headers=bearer('viewer')).status_code == 200


def test_authenticated_background_audit_and_officer_decision(secure):
    ws = secure.get('/api/intelligence/workspace?snapshot_id=small-v1', headers=bearer('planner')).json()
    response = secure.post('/api/intelligence/recommend', headers=bearer('planner'), json={
        'snapshot_id': 'small-v1', 'evidence_id': ws['evidence']['id']})
    secure.headers.update(bearer('planner'))
    rid = wait(secure, response)
    response = secure.post(f'/api/intelligence/recommendations/{rid}/decision', headers=bearer('officer'),
                           json={'action': 'approve', 'reason': 'Reviewed evidence and constraints'})
    assert response.status_code == 200, response.text
    events = secure.get('/api/admin/audit', headers=bearer('admin')).json()
    created = next(e for e in events if e['kind'] == 'recommendation-created')
    approved = next(e for e in events if e['kind'] == 'recommendation-approved')
    assert created['data']['actor'] == 'planner'
    assert approved['data']['actor'] == 'officer'
    assert approved['data']['request_id'] == response.headers['X-Request-ID']
    assert approved['data']['division'] == 'division-a'


def test_production_configuration_fails_closed(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('AUTH_MODE', 'demo')
    with pytest.raises(RuntimeError, match='Production requires'):
        Settings.load()
    monkeypatch.setenv('AUTH_MODE', 'supabase')
    monkeypatch.setenv('SUPABASE_URL', 'https://example.supabase.co')
    monkeypatch.setenv('SUPABASE_PUBLISHABLE_KEY', 'sb_secret_do_not_expose')
    with pytest.raises(RuntimeError, match='publishable key'):
        Settings.load()
    monkeypatch.setenv('SUPABASE_PUBLISHABLE_KEY', 'sb_publishable_test')
    monkeypatch.setenv('DEPLOYMENT_DIVISION', 'division-a')
    monkeypatch.setenv('CORS_ORIGINS', 'https://rail.example')
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///demo.db')
    with pytest.raises(RuntimeError, match='PostgreSQL'):
        Settings.load()
    monkeypatch.setenv('DATABASE_URL', 'postgresql+psycopg://host/db?sslmode=verify-full')
    assert Settings.load().environment == 'production'


@pytest.fixture
def local(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTH_MODE', 'demo')
    monkeypatch.setenv('AI_DATA_POLICY', 'disabled')
    with TestClient(create_app('sqlite:///' + str(tmp_path/'platform.db'))) as client:
        yield client


def recommendation(client):
    ws = client.get('/api/intelligence/workspace?snapshot_id=small-v1').json()
    return wait(client, client.post('/api/intelligence/recommend', json={'snapshot_id': 'small-v1', 'evidence_id': ws['evidence']['id']}))


def test_real_provider_contract_guards_and_persisted_quota(local, monkeypatch):
    rid = recommendation(local)
    path = f'/api/ai/recommendations/{rid}/explain'
    assert local.post(path).status_code == 503
    monkeypatch.setenv('OPENAI_API_KEY', 'test-private-key')
    monkeypatch.setenv('OPENAI_MODEL', 'configured-model')
    monkeypatch.setenv('AI_DATA_POLICY', 'synthetic')
    monkeypatch.setenv('AI_DAILY_CALL_LIMIT', '2')
    calls = []
    original_post = httpx.Client.post
    def post(self, url, **kwargs):
        if url != 'https://api.openai.com/v1/responses':
            return original_post(self, url, **kwargs)
        headers, json = kwargs['headers'], kwargs['json']
        assert url == 'https://api.openai.com/v1/responses'
        assert json['store'] is False and json['text']['format']['strict'] is True
        assert 'tools' not in json
        evidence = __import__('json').loads(json['input'])
        calls.append(evidence)
        output = {'summary': 'Review the supplied evidence.', 'findings': [{'finding': 'A supplied work item needs review',
                  'evidence_ids': [evidence['evidence_ids'][0] if len(calls) == 1 else 'invented-id']}],
                  'uncertainties': ['Officer review required'], 'review_required': False}
        return httpx.Response(200, json={'id': 'provider-id', 'status': 'completed', 'usage': {'total_tokens': 100},
            'output': [{'content': [{'type': 'output_text', 'text': __import__('json').dumps(output)}]}]})
    monkeypatch.setattr(httpx.Client, 'post', post)
    result = local.post(path)
    assert result.status_code == 200, result.text
    assert result.json()['output']['review_required'] is True
    assert local.post(path).status_code == 502
    assert local.post(path).status_code == 429
    assert len(calls) == 2
    history = local.get('/api/ai/history').text
    assert 'test-private-key' not in history and 'input' not in history.replace('input_reference', '')
    assert local.get(f'/api/intelligence/recommendations/{rid}').json()['review_status'] == 'pending'


def test_free_text_requires_authorized_policy_and_exact_quotes(local, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-private-key'); monkeypatch.setenv('OPENAI_MODEL', 'configured-model')
    monkeypatch.setenv('AI_DATA_POLICY', 'synthetic')
    path = '/api/ai/nlp/small-v1'
    assert local.post(path, json={'text': 'Signal failure for 20 minutes.'}).status_code == 403
    monkeypatch.setenv('AI_DATA_POLICY', 'authorized')
    original_post = httpx.Client.post
    def post(self, url, **kwargs):
        if url != 'https://api.openai.com/v1/responses':
            return original_post(self, url, **kwargs)
        return httpx.Response(200, json={'status': 'completed', 'output': [{'content': [{'type': 'output_text',
            'text': json.dumps({'fields': [{'field': 'cause', 'value': 'Flooding', 'quote': 'invented flooding'}], 'uncertainties': []})}]}]})
    monkeypatch.setattr(httpx.Client, 'post', post)
    assert local.post(path, json={'text': 'Signal failure for 20 minutes.'}).status_code == 502


def test_automation_is_idempotent_and_only_drafts_approved_plans(local):
    rid = recommendation(local)
    local.post('/api/admin/automation/config', json={'enabled': False, 'prepare_reports': True, 'interval_minutes': 5})
    assert not local.post('/api/admin/automation/run').json()['report_ids']
    local.post(f'/api/intelligence/recommendations/{rid}/decision', json={'action': 'approve', 'reason': 'Review complete'})
    first = local.post('/api/admin/automation/run').json()
    assert first['status'] == 'succeeded' and len(first['report_ids']) == 2
    assert not local.post('/api/admin/automation/run').json()['report_ids']
    assert len(local.get('/api/intelligence/reports?snapshot_id=small-v1').json()) == 2
    assert local.get(f'/api/intelligence/recommendations/{rid}').json()['review_status'] == 'approved'


def test_duration_learning_is_chronological_and_does_not_use_future_records(local):
    result = local.post('/api/ai/models/presentation-v1/train')
    if result.status_code == 404:
        sid = next(c['snapshot_id'] for c in local.get('/api/context').json()['corridors'] if c['id'] == 'presentation')
        result = local.post(f'/api/ai/models/{sid}/train')
    assert result.status_code == 200, result.text
    assert result.json()['status'] == 'evaluation only'
    assert not set(result.json()['training_ids']) & set(result.json()['holdout_ids'])
    cutoff = datetime.now(timezone.utc)
    records = [dict(id=str(i), planned_minutes=20+i, actual_minutes=30+i, weather='clear',
                    completed_at=(cutoff-timedelta(days=40-i)).isoformat()) for i in range(40)]
    future = {**records[-1], 'id': 'future', 'actual_minutes': 10000, 'completed_at': (cutoff+timedelta(days=1)).isoformat()}
    fitted = train(records+[future], cutoff, 'test')
    assert 'future' not in fitted['training_ids'] + fitted['holdout_ids']
    assert fitted['mae_minutes'] < fitted['engineering_baseline_mae']


def test_interrupted_external_calls_and_automation_are_visible_after_restart(local):
    from app.domain import utcnow
    store = local.app.state.store
    store.put('ai_call', {'id': 'interrupted-ai', 'status': 'started', 'created_at': utcnow()})
    store.put('automation_run', {'id': 'interrupted-monitor', 'status': 'running', 'created_at': utcnow()})
    store.init()
    assert store.get('interrupted-ai')['status'] == 'failed'
    assert store.get('interrupted-monitor')['status'] == 'failed'
    assert len(store.all('ai_call')) == 1  # Restart does not reset the provider call budget.
