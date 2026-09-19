import json
import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.persistence import LoginName, Store
from app.security import Settings
from app.usernames import INVALID_LOGIN
from test_administration import controlled, ADMIN, OTHER


def claim(client, username='rail.operator', expected=None, uid=ADMIN):
    return client.patch('/api/auth/username', headers={'Authorization': 'Bearer '+uid},
                        json={'username': username, 'expected_username': expected})


@pytest.mark.parametrize('role', ['viewer','planner','officer','admin'])
def test_all_roles_can_claim_only_their_own_username(controlled, role):
    client, users, _ = controlled
    users[ADMIN]['app_metadata']['railblox_role'] = role
    assert client.get('/api/auth/username').json() == {'username': None, 'enabled': True}
    result = claim(client, ' Rail.Operator ')
    assert result.status_code == 200, result.text
    assert result.json()['username'] == 'rail.operator'
    assert client.get('/api/auth/username').json()['username'] == 'rail.operator'
    assert claim(client, 'new.name', 'wrong.previous').status_code == 409
    assert claim(client, 'new.name', 'rail.operator').status_code == 200
    assert users[ADMIN]['app_metadata']['railblox_role'] == role


def test_unique_canonical_names_and_database_constraint(controlled):
    client, users, _ = controlled
    users[OTHER]['app_metadata'] = dict(railblox_role='viewer',railblox_division='division-a')
    assert claim(client).status_code == 200
    assert claim(client, 'RAIL.OPERATOR', uid=OTHER).status_code == 409
    with client.app.state.store.session() as session:
        session.add(LoginName(user_id=OTHER, username='rail.operator', updated_at='now'))
        with pytest.raises(IntegrityError):
            session.commit()
    with client.app.state.store.session() as session:
        assert len(list(session.scalars(select(LoginName)))) == 1
    with client.app.state.store.session() as session:
        session.add(LoginName(user_id=OTHER, username='RAIL.OPERATOR', updated_at='now'))
        with pytest.raises(IntegrityError):
            session.commit()
    assert client.get('/api/auth/username',headers={'Authorization':'Bearer '+OTHER}).json()['username'] is None


@pytest.mark.parametrize('name', ['admin','RAILBLOX','ab','9first','has space','üsername','user@example.test'])
def test_invalid_and_reserved_names(controlled,name):
    client, _, _ = controlled
    assert claim(client,name).status_code == 422


def test_unverified_pending_and_unauthenticated_cannot_claim(controlled):
    client, users, _ = controlled
    assert claim(client, uid=OTHER).status_code == 403  # pending account
    users[ADMIN]['confirmed_at'] = None
    assert claim(client).status_code == 403
    client.headers.pop('Authorization')
    assert client.patch('/api/auth/username',json={'username':'another'}).status_code == 401
    assert client.get('/api/auth/username').status_code == 401


def test_username_login_uses_current_email_and_provider_password(controlled,monkeypatch):
    client, users, calls = controlled
    assert claim(client).status_code == 200
    users[ADMIN]['email'] = 'changed@example.test'
    passwords=[]
    async def post(self,url,**kwargs):
        assert url.endswith('/auth/v1/token?grant_type=password')
        assert kwargs['headers'] == {'apikey':'sb_publishable_test'}
        passwords.append(kwargs['json'])
        return httpx.Response(200,json={'user':{'id':ADMIN},'access_token':'session-access','refresh_token':'session-refresh','extra':'not returned'})
    monkeypatch.setattr(httpx.AsyncClient,'post',post)
    client.headers.pop('Authorization')
    result=client.post('/api/auth/username-login',json={'username':'RAIL.OPERATOR','password':'test-secret'})
    assert result.status_code == 200,result.text
    assert result.json() == {'access_token':'session-access','refresh_token':'session-refresh'}
    assert result.headers['cache-control'] == 'no-store'
    assert passwords == [{'email':'changed@example.test','password':'test-secret'}]
    assert calls[-1][1].endswith('/admin/users/'+ADMIN)
    events=client.app.state.store.events()
    assert any(e['kind']=='username-updated' for e in events)
    assert not any(secret in json.dumps(events) for secret in ['test-secret','session-access','session-refresh'])


def test_login_failures_do_not_reveal_identity_or_upstream_payload(controlled,monkeypatch):
    client, users, _ = controlled
    assert claim(client).status_code == 200
    async def post(self,*args,**kwargs):
        return httpx.Response(400,json={'error_description':'admin@example.test private details'})
    monkeypatch.setattr(httpx.AsyncClient,'post',post)
    for name in ['rail.operator','no.such.user']:
        result=client.post('/api/auth/username-login',json={'username':name,'password':'test-secret'})
        assert result.status_code == 401 and result.json()['message'] == INVALID_LOGIN
        assert 'admin@example.test' not in result.text and 'test-secret' not in result.text
    result=client.post('/api/auth/username-login',json={'username':'rail.operator','password':'test-secret','role':'admin'})
    assert result.status_code == 401 and 'test-secret' not in result.text
    async def wrong_user(self,*args,**kwargs):
        return httpx.Response(200,json={'user':{'id':OTHER},'access_token':'do-not-return','refresh_token':'secret'})
    monkeypatch.setattr(httpx.AsyncClient,'post',wrong_user)
    result=client.post('/api/auth/username-login',json={'username':'rail.operator','password':'test-secret'})
    assert result.status_code == 401 and 'do-not-return' not in result.text


def test_login_limits_and_oversized_body(controlled,monkeypatch):
    client, _, _ = controlled
    async def post(self,*args,**kwargs): return httpx.Response(400)
    monkeypatch.setattr(httpx.AsyncClient,'post',post)
    for _ in range(8):
        assert client.post('/api/auth/username-login',json={'username':'unknown.name','password':'wrong'}).status_code == 401
    limited=client.post('/api/auth/username-login',json={'username':'UNKNOWN.NAME','password':'wrong'})
    assert limited.status_code == 429 and limited.headers['Retry-After'] == '60'
    assert client.post('/api/auth/username-login',content=b'x'*4097).status_code == 413


def test_registry_survives_store_restart(controlled):
    client, _, _ = controlled
    assert claim(client).status_code == 200
    store=Store(str(client.app.state.store.engine.url));store.init()
    with store.session() as session:
        assert session.get(LoginName,ADMIN).username == 'rail.operator'
    store.engine.dispose()


def test_production_mfa_default_and_explicit_testing_override(monkeypatch):
    import dotenv
    monkeypatch.setattr(dotenv,'load_dotenv',lambda *a,**k:None)
    for key,value in {'APP_ENV':'production','AUTH_MODE':'supabase','DEPLOYMENT_DIVISION':'testing',
        'SUPABASE_URL':'https://example.supabase.co','SUPABASE_PUBLISHABLE_KEY':'sb_publishable_test',
        'CORS_ORIGINS':'https://rail.example.test',
        'DATABASE_URL':'postgresql+psycopg://test:test@localhost/test?sslmode=verify-full'}.items():
        monkeypatch.setenv(key,value)
    monkeypatch.delenv('REQUIRE_MFA',raising=False)
    assert Settings.load().require_mfa is True
    monkeypatch.setenv('REQUIRE_MFA','false')
    assert Settings.load().require_mfa is False
    monkeypatch.setenv('REQUIRE_MFA','true')
    assert Settings.load().require_mfa is True
    monkeypatch.setenv('REQUIRE_MFA','typo')
    with pytest.raises(RuntimeError,match='REQUIRE_MFA'):
        Settings.load()


def test_mfa_off_still_enforces_authentication_and_roles(controlled):
    client, users, _ = controlled
    me=client.get('/api/auth/me').json()
    assert me['mfa_required'] is False and me['mfa_policy_enabled'] is False
    assert client.get('/api/context').status_code == 200
    users[ADMIN]['app_metadata']['railblox_role']='viewer'
    assert client.post('/api/plans/any/approve',json={}).status_code == 403
    assert client.get('/api/context',headers={'Authorization':'Bearer invalid'}).status_code == 401
