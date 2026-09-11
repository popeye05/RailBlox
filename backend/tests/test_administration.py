import base64
import json
from uuid import UUID
import httpx
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.administration import AuthAdmin
from app.security import Settings
from app.bootstrap_admin import bootstrap

ADMIN='00000000-0000-0000-0000-000000000001'
OTHER='00000000-0000-0000-0000-000000000002'


@pytest.fixture
def controlled(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTH_MODE','supabase')
    monkeypatch.setenv('SUPABASE_URL','https://identity.example.supabase.co')
    monkeypatch.setenv('SUPABASE_PUBLISHABLE_KEY','sb_publishable_test')
    monkeypatch.setenv('SUPABASE_SERVICE_ROLE_KEY','private-admin-key')
    monkeypatch.setenv('DEPLOYMENT_DIVISION','division-a')
    users={ADMIN:dict(id=ADMIN,email='admin@example.test',confirmed_at='2026-01-01',app_metadata={'railblox_role':'admin','railblox_division':'division-a'},user_metadata={}),
           OTHER:dict(id=OTHER,email='new@example.test',confirmed_at='2026-01-01',app_metadata={},user_metadata={'full_name':'New Colleague','requested_role':'admin','date_of_birth':'1990-01-01'})}
    calls=[]
    async def get(self,url,headers):
        token=headers['Authorization'][7:]
        if token=='invalid':return httpx.Response(401)
        if token.startswith('ey'):
            payload=token.split('.')[1]; uid=json.loads(base64.urlsafe_b64decode(payload+'='*(-len(payload)%4)))['sub']
        else:uid=token
        return httpx.Response(200,json=users[uid])
    async def request(self,method,url,**kwargs):
        calls.append((method,url,kwargs))
        assert kwargs['headers']['apikey']=='private-admin-key'
        if url.endswith('/admin/users'):
            page=kwargs['params']['page']; size=kwargs['params']['per_page']
            return httpx.Response(200,json={'users':list(users.values())[(page-1)*size:page*size]})
        if url.endswith('/invite'):return httpx.Response(200,json=users[OTHER])
        uid=url.rsplit('/',1)[-1]
        if method=='PUT':users[uid]['app_metadata'].update(kwargs['json']['app_metadata'])
        return httpx.Response(200,json=users[uid])
    monkeypatch.setattr(httpx.AsyncClient,'get',get)
    monkeypatch.setattr(httpx.AsyncClient,'request',request)
    with TestClient(create_app('sqlite:///'+str(tmp_path/'access.db'))) as client:
        client.headers.update({'Authorization':'Bearer '+ADMIN})
        yield client,users,calls


def change(role,expected=None,division=None):
    return {'role':role,'expected_role':expected,'expected_division':division,'reason':'Reviewed division assignment'}


def test_registration_is_pending_and_metadata_cannot_elevate(controlled):
    client,_,_=controlled
    me=client.get('/api/auth/me',headers={'Authorization':'Bearer '+OTHER}).json()
    assert me['access_pending'] and me['role'] is None and 'date_of_birth' not in me
    assert client.get('/api/context',headers={'Authorization':'Bearer '+OTHER}).status_code==403
    listing=client.get('/api/admin/users?per_page=1').json()
    assert listing['has_more'] and len(listing['users'])==1
    second=client.get('/api/admin/users?page=2&per_page=1').json()
    assert second['users'][0]['id']==OTHER and 'date_of_birth' not in second['users'][0]
    assert client.patch('/api/admin/users/'+OTHER,json={}).status_code==422


def test_grant_revoke_stale_self_and_foreign_division(controlled):
    client,users,calls=controlled
    result=client.patch('/api/admin/users/'+OTHER,json=change('planner'))
    assert result.status_code==200,result.text
    assert client.get('/api/context',headers={'Authorization':'Bearer '+OTHER}).status_code==200
    assert client.patch('/api/admin/users/'+OTHER,json=change('officer')).status_code==409
    assert client.patch('/api/admin/users/'+OTHER,json=change(None,'planner','division-a')).status_code==200
    assert users[OTHER]['app_metadata']['railblox_role'] is None
    assert client.get('/api/context',headers={'Authorization':'Bearer '+OTHER}).status_code==403
    assert client.patch('/api/admin/users/'+ADMIN,json=change('viewer','admin','division-a')).status_code==409
    users[OTHER]['app_metadata']={'railblox_role':'admin','railblox_division':'foreign'}
    assert client.patch('/api/admin/users/'+OTHER,json=change('viewer','admin','foreign')).status_code==403
    assert all(u['id']!=OTHER for u in client.get('/api/admin/users').json()['users'])
    events=client.get('/api/admin/audit').json()
    updates=[e for e in events if e['kind']=='user-access-updated']
    assert len(updates)==2 and all(e['data']['actor']==ADMIN for e in updates)
    assert '1990-01-01' not in json.dumps(events)


def test_invitation_does_not_assign_access_and_email_confirmation_required(controlled):
    client,users,calls=controlled
    users[OTHER]['confirmed_at']=None
    assert client.patch('/api/admin/users/'+OTHER,json=change('admin')).status_code==409
    result=client.post('/api/admin/invitations',json={'email':'new@example.test','name':'Colleague','requested_role':'officer'})
    assert result.status_code==200
    sent=calls[-1][2]['json']
    assert 'app_metadata' not in sent and not users[OTHER]['app_metadata']


def test_mfa_requires_verified_bearer_assurance(controlled,monkeypatch,tmp_path):
    _,users,_=controlled
    monkeypatch.setenv('REQUIRE_MFA','true')
    def jwt(aal):
        def enc(value):return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip('=')
        return enc({'alg':'RS256'})+'.'+enc({'sub':ADMIN,'aal':aal})+'.test-signature'
    with TestClient(create_app('sqlite:///'+str(tmp_path/'mfa.db'))) as client:
        for token in [ADMIN,jwt('aal1')]:
            assert client.get('/api/auth/me',headers={'Authorization':'Bearer '+token}).status_code==200
            assert client.get('/api/context',headers={'Authorization':'Bearer '+token}).status_code==403
        assert client.get('/api/context',headers={'Authorization':'Bearer '+jwt('aal2')}).status_code==200
        assert client.get('/api/context',headers={'Authorization':'Bearer invalid'}).status_code==401


@pytest.mark.parametrize('role',['viewer','planner'])
def test_officer_checks_cannot_be_forged(controlled,role):
    client,users,_=controlled
    users[OTHER]['app_metadata']={'railblox_role':role,'railblox_division':'division-a'}
    for route in ['/api/plans/any/validate','/api/benchmarks','/api/plans/any/finalize','/api/plans/any/revise']:
        assert client.post(route,headers={'Authorization':'Bearer '+OTHER},json={}).status_code==403


def test_bootstrap_refuses_existing_admin(controlled):
    import asyncio
    with pytest.raises(ValueError,match='already exists'):
        asyncio.run(bootstrap(Settings.load(),UUID(OTHER),'new@example.test'))


def test_provider_errors_do_not_leak_secrets(controlled,monkeypatch):
    client,_,_=controlled
    async def bad(self,*args,**kwargs):raise httpx.ConnectError('private-admin-key')
    monkeypatch.setattr(httpx.AsyncClient,'request',bad)
    response=client.get('/api/admin/users')
    assert response.status_code==503 and 'private-admin-key' not in response.text


def test_unconfirmed_access_attempt_remains_auditable(controlled,monkeypatch):
    client,_,_=controlled
    original=AuthAdmin.request
    async def lost_response(self,method,path,payload=None,params=None):
        result=await original(self,method,path,payload,params)
        if method=='PUT':
            from fastapi import HTTPException
            raise HTTPException(503,'Response lost after provider processed the update')
        return result
    monkeypatch.setattr(AuthAdmin,'request',lost_response)
    assert client.patch('/api/admin/users/'+OTHER,json=change('planner')).status_code==503
    events=client.get('/api/admin/audit').json()
    assert any(e['kind']=='user-access-requested' for e in events)
    assert any(e['kind']=='user-access-unconfirmed' for e in events)
    assert not any(e['kind']=='user-access-updated' for e in events)


def test_bootstrap_preview_does_not_write_and_apply_is_audited(controlled,monkeypatch,tmp_path):
    import asyncio
    from app.persistence import Store
    _,users,calls=controlled
    users[ADMIN]['app_metadata']={}
    monkeypatch.setenv('DATABASE_URL','sqlite:///'+str(tmp_path/'bootstrap.db'))
    result=asyncio.run(bootstrap(Settings.load(),UUID(OTHER),'new@example.test'))
    assert result.startswith('Review:') and not any(c[0]=='PUT' for c in calls)
    asyncio.run(bootstrap(Settings.load(),UUID(OTHER),'new@example.test',apply=True))
    assert users[OTHER]['app_metadata']['railblox_role']=='admin'
    store=Store()
    assert {e['kind'] for e in store.events()}=={'admin-bootstrap-requested','admin-bootstrap-completed'}
    store.engine.dispose()


def test_edited_profile_metadata_is_bounded(controlled):
    client,users,_=controlled
    users[OTHER]['user_metadata']={'full_name':{'nested':'unsafe'},'requested_role':['admin'],'date_of_birth':'1990-01-01'}
    response=client.get('/api/admin/users')
    assert response.status_code==200
    other=next(u for u in response.json()['users'] if u['id']==OTHER)
    assert other['name']=='' and other['requested_role']=='viewer' and 'date_of_birth' not in other


def test_authenticated_limiter_rejects_excess_requests(monkeypatch,tmp_path):
    monkeypatch.setenv('API_RATE_LIMIT_PER_MINUTE','2')
    with TestClient(create_app('sqlite:///'+str(tmp_path/'limit.db'))) as client:
        assert client.get('/api/status').status_code==200
        assert client.get('/api/status').status_code==200
        assert client.get('/api/status').status_code==429
