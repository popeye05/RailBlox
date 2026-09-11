from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.fixtures import acceptance
from app.intelligence import seed_evidence, intelligence_rows, duration_estimate, extract_text, freshness, planning_snapshot
from app.solver import solve
from app.validator import validate
from test_api import wait


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app('sqlite:///'+str(tmp_path/'intel.db'))) as c:
        yield c


def test_missing_factors_unknown_text_and_small_samples_are_not_confident():
    s=acceptance(); e=seed_evidence(s)
    a=next(r for r in intelligence_rows(s,e) if r['task_id']=='A')
    assert a['priority']['score'] is None
    assert a['priority']['score_high']-a['priority']['score_low']==10
    assert a['duration']['planning_minutes']>=a['duration']['planned']
    assert duration_estimate(s.tasks[0],[])['high'] is None
    result=extract_text('No signal failure at S1-UP; crew unavailable for 20 minutes.',['S1-UP'])
    assert next(m for m in result['matches'] if m['cause']=='signal failure')['negated']
    assert result['durations'][0]['minutes']==20
    assert result['severity']=='Not inferred'
    assert extract_text('Something happened',[])['matches']==[]


def test_weather_holds_reach_solver_and_independent_validator():
    s=acceptance(); e=seed_evidence(s); rows=intelligence_rows(s,e)
    derived=planning_snapshot(s,e,rows); plan=solve(derived)
    assert plan['validation']['valid']
    assert all(p['end']<=195 for p in plan['packages'] if 'S1-UP' in p['sections'])
    changed=plan.copy(); changed['packages']=[dict(p,end=205) if 'S1-UP' in p['sections'] else p for p in plan['packages']]
    assert any(v['rule_id']=='SYNTHETIC-PROTECTION' for v in validate(derived,changed)['violations'])
    # Overlapping source holds form a union rather than conflict with each other.
    derived.protected_intervals.append(dict(id='duplicate',section='S1-UP',start=200,end=250,kind='Existing block'))
    assert solve(derived)['validation']['valid']


def test_evidence_freshness_and_references(client):
    ws=client.get('/api/intelligence/workspace?snapshot_id=small-v1').json(); e=ws['evidence']
    e['blocks'][0]['section']='UNKNOWN'
    assert client.post('/api/intelligence/evidence',json={'expected_evidence':e['id'],'evidence':e}).status_code==422
    e['blocks'][0]['section']='S1-DN'; e['feeds'][0]['state']='unavailable'
    updated=client.post('/api/intelligence/evidence',json={'expected_evidence':e['id'],'evidence':e})
    assert updated.status_code==200
    body={'snapshot_id':'small-v1','evidence_id':updated.json()['id']}
    assert client.post('/api/intelligence/recommend',json=body).status_code==409
    assert client.post('/api/intelligence/evidence',json={'expected_evidence':e['id'],'evidence':e}).status_code==409
    model=seed_evidence(acceptance()); model.feeds[0].received_at-=timedelta(hours=3)
    assert freshness(model)[0]['state']=='stale'


def test_full_recommendation_review_outcome_and_report(client):
    base='/api/intelligence'
    workspace=client.get(base+'/workspace?snapshot_id=small-v1').json()
    rid=wait(client,client.post(base+'/recommend',json={'snapshot_id':'small-v1','evidence_id':workspace['evidence']['id']}))
    rec=client.get(base+'/recommendations/'+rid).json()
    assert rec['plan']['validation']['valid']
    assert client.post(f'/api/plans/{rec["plan_id"]}/approve',json={'expected_snapshot':rec['plan']['snapshot_id'],'reason':'bypass'}).status_code==409
    assert client.post(f'{base}/recommendations/{rid}/decision',json={'action':'approve','reason':'Reviewed the modeled constraints and uncertainty'}).status_code==200
    a=rec['plan']['assignments'][0]
    outcome={'task_id':a['task_id'],'actual_start':a['start'],'actual_end':a['end']+20,'observed_at':a['end']+20,'narrative':'Equipment failure caused 20 minutes delay.','delay_minutes':20}
    assert client.post(f'{base}/recommendations/{rid}/outcomes',json=outcome).status_code==200
    assert client.post(f'{base}/recommendations/{rid}/outcomes',json=outcome).status_code==409
    assert client.post(f'{base}/recommendations/{rid}/decision',json={'action':'reject','reason':'duplicate'}).status_code==409
    report=client.post(base+'/reports',json={'recommendation_id':rid,'kind':'PAM'}).json()
    assert any(row['actual_minutes'] is not None for row in report['rows'])
    assert report['missing']
    reviewed=client.post(f'{base}/reports/{report["id"]}/review',json={'summary':'Reviewed local draft; outstanding actual results remain missing.','reason':'Checked source references'})
    assert reviewed.json()['status']=='reviewed draft'
    assert client.get(f'{base}/reports/{report["id"]}/export').json()['reviews']
    # Outcomes are stored, but cannot leak into analysis before they happened.
    after=client.get(base+'/workspace?snapshot_id=small-v1').json()
    assert len(after['outcomes'])==1
    assert after['rows'][0]['duration']['samples']==workspace['rows'][0]['duration']['samples']


def test_changed_evidence_blocks_approval_and_rejection_persists(client):
    base='/api/intelligence'
    e=client.get(base+'/workspace?snapshot_id=small-v1').json()['evidence']
    rid=wait(client,client.post(base+'/recommend',json={'snapshot_id':'small-v1','evidence_id':e['id']}))
    e['assessments']['A']['security']=2
    assert client.post(base+'/evidence',json={'expected_evidence':e['id'],'evidence':e}).status_code==200
    assert client.post(f'{base}/recommendations/{rid}/decision',json={'action':'approve','reason':'stale approval'}).status_code==409
    assert client.post(f'{base}/recommendations/{rid}/decision',json={'action':'reject','reason':'Superseded source evidence'}).status_code==200
    assert client.get(f'{base}/recommendations/{rid}').json()['review_status']=='rejected'


def test_override_cannot_silently_ignore_work_outside_horizon(client):
    base='/api/intelligence'
    evidence=client.get(base+'/workspace?snapshot_id=presentation-v1').json()['evidence']
    response=client.post(base+'/recommend',json={'snapshot_id':'presentation-v1','evidence_id':evidence['id'],
                                                'day':0,'horizon':7,'task_id':'PM-099','window_id':'PW-00-0',
                                                'reason':'Try an out of horizon task'})
    assert response.status_code==422
    assert 'outside' in response.json()['message']


def test_snapshot_protection_and_roams_contract_survive_storage(client):
    sample=client.get('/api/samples/ROAMS?format=json')
    assert sample.status_code==200
    assert sample.json()[0]['source_record_id']=='ROAMS-001'
    e=client.get('/api/intelligence/workspace?snapshot_id=small-v1').json()['evidence']
    assert e['weather'][0]['section']=='S1-UP'
    rid=wait(client,client.post('/api/intelligence/recommend',json={'snapshot_id':'small-v1','evidence_id':e['id']}))
    r=client.get('/api/intelligence/recommendations/'+rid).json()
    stored=client.get('/api/snapshots/'+r['plan']['snapshot_id']).json()
    assert any(p['id']=='WX-01' for p in stored['protected_intervals'])
    regenerated=wait(client,client.post('/api/plans/generate',json={'snapshot_id':stored['id']}))
    assert client.post(f'/api/plans/{regenerated}/approve',json={'expected_snapshot':stored['id'],'reason':'Attempt generic approval'}).status_code==409
