import json
import time
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.adapters import safe_csv


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app('sqlite:///'+str(tmp_path/'test.db'))) as c: yield c


def wait(client,response):
    assert response.status_code==202,response.text
    for _ in range(200):
        state=client.get('/api/runs/'+response.json()['id']).json()
        if state['status']=='failed': pytest.fail(state['error'])
        if state['status']=='succeeded': return state['result_id']
        time.sleep(.05)
    pytest.fail('Job did not finish')


def current(client): return next(c for c in client.get('/api/context').json()['corridors'] if c['id']=='small')['snapshot_id']


def test_workflow_approval_stale_and_export(client):
    context=client.get('/api/context').json(); p=next(p for p in context['plans'] if p['corridor']=='small')
    result=wait(client,client.post(f'/api/plans/{p["id"]}/opportunities',json={'window_id':'W1'}))
    assert any(r['accepted'] for r in client.get('/api/opportunities/'+result).json()['records'])
    added=wait(client,client.post(f'/api/plans/{p["id"]}/revise',json={'expected_snapshot':current(client),'task_ids':['B','C'],'window_id':'W1'}))
    scenario=client.post('/api/scenarios',json={'baseline_id':added,'kind':'shorten','target':'W1','minutes':20}).json()
    repaired=wait(client,client.post(f'/api/scenarios/{scenario["id"]}/repair'))
    plan=client.get('/api/plans/'+repaired).json(); assert plan['validation']['valid']; assert 'C' in plan['metrics']['changed_task_ids']
    assert client.post(f'/api/plans/{repaired}/validate').json()['valid']
    assert client.post(f'/api/plans/{repaired}/approve',json={'expected_snapshot':scenario['id'],'reason':'Demo review'}).status_code==200
    assert client.get(f'/api/plans/{repaired}/export?format=json').json()['plan']['approval']=='approved'
    assert 'task_id' in client.get(f'/api/plans/{repaired}/export?format=csv').text
    old=current(client)
    resolved=client.post('/api/mappings/G/resolve',json={'expected_snapshot':old,'asset_id':'AS-S1-UP'})
    assert resolved.status_code==200
    assert not client.get('/api/plans/'+repaired).json()['current']
    assert client.post(f'/api/plans/{repaired}/approve',json={'expected_snapshot':scenario['id'],'reason':'Stale approval'}).status_code==409


def sample_row():
    return dict(source_record_id='import-01',asset_id='AS-S2-UP',section='S2-UP',line='UP',chainage=12.5,chainage_unit='km',department='ENG',title='Imported inspection',duration=20,earliest='2026-09-10T07:30:00+05:30',due='2026-09-10T09:30:00+05:30',source_timestamp='2026-09-09T12:00:00Z',resources=['ENG-1'],mandatory=False,isolation=['ISO-2'],access=['traffic'])


def do_import(client,row):
    sid=current(client)
    preview=client.post('/api/imports/preview',data={'source':'TMS','snapshot_id':sid},files={'file':('sample.json',json.dumps([row]).encode(),'application/json')})
    assert preview.status_code==200,preview.text
    result=client.post('/api/imports/'+preview.json()['id']+'/commit',json={'expected_snapshot':sid,'mapping_confirmed':True})
    assert result.status_code==200,result.text
    return result.json()


def test_import_idempotency_and_validation(client):
    row=sample_row(); first=do_import(client,row); second=do_import(client,row)
    assert first['inserts']==1; assert second['inserts']==0; assert second['unchanged']==1
    assert client.get('/api/tasks',params={'snapshot_id':current(client)}).json()['total']==11
    row.pop('chainage_unit'); bad=do_import(client,row); assert bad['rejected']==1
    response=client.post('/api/imports/preview',data={'source':'TMS','snapshot_id':current(client)},files={'file':('bad.txt',b'no')})
    assert response.status_code==422; assert 'request_id' in response.json()


def test_restart_persists_mapping_plan_and_import(tmp_path):
    url='sqlite:///'+str(tmp_path/'persist.db')
    with TestClient(create_app(url)) as c:
        assert do_import(c,sample_row())['inserts']==1
        response=c.post('/api/mappings/G/resolve',json={'expected_snapshot':current(c),'asset_id':'AS-S1-UP'})
        sid=response.json()['snapshot_id']; pid=wait(c,c.post('/api/plans/generate',json={'snapshot_id':sid}))
    with TestClient(create_app(url)) as c:
        assert current(c)==sid; assert c.get('/api/plans/'+pid).status_code==200
        assert c.get('/api/mappings',params={'snapshot_id':sid}).json()==[]
        assert len(c.get('/api/imports').json())==1


def test_locked_plan_conflict_requires_revision(client):
    pid=wait(client,client.post('/api/plans/generate',json={'snapshot_id':current(client)}))
    client.post('/api/plans/'+pid+'/approve',json={'expected_snapshot':current(client),'reason':'Lock all assignments'})
    scenario=client.post('/api/scenarios',json={'baseline_id':pid,'kind':'shorten','target':'W1','minutes':20}).json()
    failed=wait(client,client.post('/api/scenarios/'+scenario['id']+'/repair'))
    p=client.get('/api/plans/'+failed).json(); assert p['solver_status']=='INFEASIBLE'
    assert client.post('/api/plans/'+failed+'/approve',json={'expected_snapshot':scenario['id'],'reason':'Cannot approve'}).status_code==409
    revision=wait(client,client.post('/api/plans/'+failed+'/revise',json={'expected_snapshot':scenario['id'],'release_unstarted':True}))
    assert client.get('/api/plans/'+revision).json()['validation']['valid']


def test_deferral_only_when_finalized(client):
    sid=current(client); first=wait(client,client.post('/api/plans/generate',json={'snapshot_id':sid})); second=wait(client,client.post('/api/plans/generate',json={'snapshot_id':sid}))
    assert all(t['deferrals']==0 for t in client.get('/api/tasks',params={'snapshot_id':sid}).json()['items'])
    r=client.post(f'/api/plans/{second}/finalize',json={'expected_snapshot':sid,'reason':'End cycle'})
    assert r.status_code==200
    assert client.post(f'/api/plans/{second}/finalize',json={'expected_snapshot':r.json()['snapshot_id'],'reason':'Repeated'}).status_code==409
    assert max(t['deferrals'] for t in client.get('/api/tasks',params={'snapshot_id':current(client)}).json()['items'])==1


def test_csv_formula_safety():
    assert "'=HYPERLINK" in safe_csv([{'title':'=HYPERLINK("bad")'}])


def test_measured_benchmarks_and_export(client):
    bid=wait(client,client.post('/api/benchmarks',json={'snapshot_id':current(client)}))
    benchmark=client.get('/api/benchmarks/'+bid).json()
    assert len(benchmark['rows'])==4
    assert all(r['valid'] and r['runtime_seconds']>0 for r in benchmark['rows'])
    assert benchmark['rows'][-1]['scenario_passes']==3
    assert benchmark['rows'][2]['scenario_passes']<3
    assert 'closed_section_minutes' in client.get(f'/api/benchmarks/{bid}/export?format=csv').text
    history=client.get('/api/benchmarks',params={'snapshot_id':current(client)}).json()
    assert history[0]['id']==bid


def test_move_rejection_does_not_create_plan(client):
    pid=wait(client,client.post('/api/plans/generate',json={'snapshot_id':current(client)}))
    before=len(client.get('/api/plans').json())
    run=client.post(f'/api/plans/{pid}/revise',json={'expected_snapshot':current(client),'task_id':'A','window_id':'W1','start':180}).json()
    for _ in range(100):
        result=client.get('/api/runs/'+run['id']).json()
        if result['status']=='failed': break
        time.sleep(.05)
    assert result['status']=='failed'
    assert len(client.get('/api/plans').json())==before


def test_changed_raw_location_requires_new_confirmation(client):
    row=sample_row(); row['asset_id']='ambiguous-alias'; row['chainage']=12.6
    do_import(client,row)
    tid='TMS-import-01'
    resolved=client.post(f'/api/mappings/{tid}/resolve',json={'expected_snapshot':current(client),'asset_id':'AS-S2-UP'})
    assert resolved.status_code==200
    assert do_import(client,row)['unchanged']==1
    row['chainage']=12.7
    assert do_import(client,row)['updates']==1
    mappings=client.get('/api/mappings',params={'snapshot_id':current(client)}).json()
    assert any(m['id']==tid for m in mappings)


def test_openapi_publishes_plan_contract(client):
    schema=client.get('/openapi.json').json()
    assert schema['paths']['/api/plans/{id}']['get']['responses']['200']['content']['application/json']['schema']['$ref'].endswith('/PlanOutput')
    assert 'AssignmentOutput' in schema['components']['schemas']
    history=client.get('/api/tasks/A/history',params={'snapshot_id':current(client)}).json()
    assert history['plans'][0]['assignment']['window_id']=='W1'
