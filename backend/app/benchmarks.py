from time import perf_counter
from .solver import solve
from .validator import validate
from .repair import scenario_snapshot
from .domain import ScenarioRequest


def greedy(snapshot,horizon,day,departmental=False):
    from .footprints import eligible
    begun=perf_counter(); selected=set(); fixed={}; result=None
    ordered=sorted(eligible(snapshot,day,horizon),key=lambda t: ((['ENG','TRD','S&T'].index(t.department) if departmental else 0),not t.mandatory,t.due,-t.weight,t.id))
    # Required work is solved first so neither baseline obtains low cost by dropping it.
    required={t.id for t in ordered if t.mandatory}
    result=solve(snapshot,horizon,day,allowed=required,seconds=2)
    if not result['validation']['valid']: return result
    selected=required.copy(); fixed={a['task_id']:a for a in result['assignments']}
    for t in ordered:
        if t.id in selected: continue
        trial=solve(snapshot,horizon,day,allowed=selected|{t.id},locks=fixed,seconds=0.15)
        if trial['validation']['valid'] and any(a['task_id']==t.id for a in trial['assignments']):
            result=trial; selected.add(t.id); fixed={a['task_id']:a for a in result['assignments']}
    result['runtime_seconds']=round(perf_counter()-begun,4)
    return result


def benchmark(snapshot,horizon=7,day=0):
    rows=[]
    for name,method in [('Department sequential greedy',lambda:greedy(snapshot,horizon,day,True)),('Combined deadline greedy',lambda:greedy(snapshot,horizon,day)),('Joint CP-SAT',lambda:solve(snapshot,horizon,day)),('Adaptive repair planner',lambda:solve(snapshot,horizon,day))]:
        plan=method(); trials=[]
        target=next((p['window_id'] for p in plan['packages']),snapshot.windows[0].id)
        for minutes in [10,20,30]:
            changed=scenario_snapshot(snapshot,ScenarioRequest(baseline_id=plan['id'],kind='shorten',target=target,minutes=minutes))
            begun=perf_counter()
            result=solve(changed,horizon,day,baseline=plan,seconds=2) if name=='Adaptive repair planner' else plan
            validation=validate(changed,result)
            trials.append(dict(shortening_minutes=minutes,valid=validation['valid'],changed_assignments=result['metrics']['changed_assignments'],runtime_seconds=round(perf_counter()-begun,4)))
        rows.append(dict(method=name,**plan['metrics'],runtime_seconds=plan['runtime_seconds'],valid=plan['validation']['valid'],solver_status=plan['solver_status'],disruption_trials=trials,scenario_passes=sum(t['valid'] for t in trials),scenario_count=len(trials)))
    return dict(snapshot_id=snapshot.id,seed=snapshot.seed,horizon=horizon,day=day,rows=rows,notes='Three deterministic held-out window shortenings (10/20/30 minutes); these are modeled scenario checks, not simulated railway handback rates. Greedy methods reserve previously allocated task times. Unequal service coverage must be considered when comparing closure cost.')
