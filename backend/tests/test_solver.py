from copy import deepcopy
import pytest
from app.fixtures import acceptance, presentation
from app.solver import solve
from app.validator import validate
from app.metrics import union_minutes
from app.candidates import discover
from app.repair import scenario_snapshot
from app.domain import ScenarioRequest


@pytest.fixture
def source(): return acceptance()


@pytest.fixture
def full(source): return solve(source)


def test_exact_full_and_fallback(source,full):
    p=next(p for p in full['packages'] if p['window_id']=='W1')
    assert p['task_ids']==['A','B','C']; assert p['end']-p['start']==75; assert p['margin']==15
    source.windows[0].end=190
    repaired=solve(source,baseline=full)
    q=next(p for p in repaired['packages'] if p['window_id']=='W1')
    assert q['task_ids']==['A','B']; assert q['end']-q['start']==60; assert q['margin']==10
    assert repaired['validation']['valid']
    assert next(a for a in full['assignments'] if a['task_id']=='D')==next(a for a in repaired['assignments'] if a['task_id']=='D')
    assert repaired['metrics']['changed_task_ids']==['C']; assert repaired['metrics']['start_shift']==0


@pytest.mark.parametrize('case,rule',[('incompatible','INCOMPATIBLE'),('resource','CAPACITY'),('footprint','FOOTPRINT'),('train','TRAIN'),('restoration','STAGES'),('duration','DURATION'),('isolation','FOOTPRINT'),('traffic','FOOTPRINT')])
def test_independent_rejections(source,full,case,rule):
    if case=='incompatible':
        source.tasks[1].incompatible=['track']
    elif case=='resource': source.tasks[1].resources=['ENG-1']
    elif case=='footprint': source.tasks[1].section='S2-UP'
    elif case=='train': source.movements[0]['occupancies'][0].update(start=125,end=145)
    elif case=='restoration': full['packages'][0]['restoration_start']=full['packages'][0]['end']
    elif case=='duration': full['assignments'][0]['end']-=1
    elif case=='isolation': source.windows[0].isolation=[]
    elif case=='traffic': source.windows[0].access=['electrical']
    result=validate(source,full)
    assert not result['valid']; assert any(v['rule_id']=='SYNTHETIC-'+rule for v in result['violations'])


def test_unresolved_mandatory_and_impossible(source):
    source.tasks[6].mandatory=True
    p=solve(source); assert p['solver_status']=='INFEASIBLE'; assert not p['validation']['valid']
    assert p['metrics']['mandatory_met']<p['metrics']['mandatory_required']
    source.tasks[6].mandatory=False; source.tasks[0].due=1
    assert solve(source)['solver_status']=='INFEASIBLE'


def test_locks_and_started_work(source,full):
    locks={a['task_id']:a for a in full['assignments']}
    source.windows[0].end=190; source.tasks[2].started=True
    repaired=solve(source,baseline=full,locks=locks)
    assert repaired['solver_status']=='INFEASIBLE'
    assert not repaired['validation']['valid']
    assert source.tasks[2].duration==15


def test_opportunity_bundle_is_counterfactual(source):
    core=solve(source,core_only=True)
    result=discover(source,core,'W1')
    bundle=next(r for r in result['records'] if set(r['task_ids'])=={'B','C'})
    assert bundle['accepted']; assert bundle['added_closed_section_minutes']==15; assert bundle['remaining_margin']==15
    b=next(r for r in result['records'] if r['task_ids']==['B'])
    assert b['accepted']; assert b['added_closed_section_minutes']==0
    assert core['packages'][0]['task_ids']==['A']


def test_monthly_actual_horizon_and_locks():
    s=presentation(); weekly=solve(s,horizon=7); monthly=solve(s,horizon=30)
    assert weekly['validation']['valid']; assert monthly['validation']['valid']
    assert monthly['metrics']['eligible']>weekly['metrics']['eligible']
    assert any(a['start']>=7*1440 for a in monthly['assignments'])
    locks={a['task_id']:a for a in monthly['assignments'] if a['start']<7*1440}
    refined=solve(s,horizon=7,locks=locks)
    assert refined['validation']['valid']
    for a in refined['assignments']:
        if a['task_id'] in locks: assert a==locks[a['task_id']]


def test_timeout_is_unknown_not_infeasible(source):
    p=solve(source,seconds=0)
    assert p['solver_status']=='UNKNOWN'; assert p['assignments']==[]; assert not p['validation']['valid']


def test_freight_propagation(source):
    changed=scenario_snapshot(source,ScenarioRequest(baseline_id='test',kind='freight',target='FRT-01',minutes=17))
    for before,after in zip(source.movements[0]['occupancies'],changed.movements[0]['occupancies']):
        assert after['start']-before['start']==17; assert after['end']-before['end']==17


def test_union_cost():
    assert union_minutes([(10,30),(15,40),(40,50)])==40
