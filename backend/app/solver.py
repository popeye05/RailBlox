"""CP-SAT optional task intervals inside shared possession intervals.

Lexicographic stages are frozen only at their achieved value. If any stage is
merely FEASIBLE, overall outcome remains FEASIBLE and guarantees are reported.
"""
import os
import time
from uuid import uuid4
from ortools.sat.python import cp_model
from .domain import utcnow
from .footprints import eligible, incompatibility
from .validator import validate
from .metrics import metrics
from .protection import fixed_intervals


def solve(snapshot, horizon=7, day=0, baseline=None, locks=None, forced=None, core_only=False, allowed=None, seconds=None):
    begun=time.perf_counter(); limit=float(seconds if seconds is not None else os.getenv('SOLVE_SECONDS','10'))
    model=cp_model.CpModel(); lo=day*1440; hi=(day+horizon)*1440
    tasks=eligible(snapshot,day,horizon); ts={t.id:t for t in tasks}; windows=[w for w in snapshot.windows if w.start<hi and w.end>lo]
    locks=locks or {}; forced=forced or {}; selected={}; starts={}; ends={}; choices={}; pk={}; intervals={r.id:[] for r in snapshot.resources}; section_intervals={s['id']:[] for s in snapshot.sections}
    for t in tasks:
        selected[t.id]=model.new_bool_var('selected_'+t.id)
        starts[t.id]=model.new_int_var(lo,hi,'start_'+t.id); ends[t.id]=model.new_int_var(lo,hi,'end_'+t.id)
        model.add(ends[t.id]==starts[t.id]+t.duration).only_enforce_if(selected[t.id])
        model.add(starts[t.id]==lo).only_enforce_if(selected[t.id].Not()); model.add(ends[t.id]==lo).only_enforce_if(selected[t.id].Not())
        model.add(starts[t.id]>=t.earliest).only_enforce_if(selected[t.id]); model.add(ends[t.id]<=t.due).only_enforce_if(selected[t.id])
        if t.mandatory or t.started or t.id in locks or t.id in forced: model.add(selected[t.id]==1)
        if (core_only and not t.mandatory) or (allowed is not None and t.id not in allowed): model.add(selected[t.id]==0)
        for r_id in t.resources:
            r=next((r for r in snapshot.resources if r.id==r_id),None)
            if not r: model.add(selected[t.id]==0); continue
            resource_end=model.new_int_var(lo,hi+r.setup,'resource_end_'+t.id+r.id)
            model.add(resource_end==ends[t.id]+r.setup)
            intervals[r.id].append(model.new_optional_interval_var(starts[t.id],t.duration+r.setup,resource_end,selected[t.id],'resource_'+t.id+r.id))
            calendars=[]
            for a,b in r.availability:
                v=model.new_bool_var('calendar_'+t.id+r.id+str(a)); calendars.append(v)
                model.add(starts[t.id]>=a).only_enforce_if(v); model.add(resource_end<=b).only_enforce_if(v)
            model.add(sum(calendars)==selected[t.id])
    for w in windows:
        active=model.new_bool_var('active_'+w.id); ps=model.new_int_var(max(lo,w.start),min(hi,w.end),'package_start_'+w.id); pe=model.new_int_var(max(lo,w.start),min(hi,w.end),'package_end_'+w.id)
        duration=model.new_int_var(0,w.end-w.start,'duration_'+w.id)
        model.add(pe==ps+duration); model.add(duration==0).only_enforce_if(active.Not())
        model.add(ps==max(lo,w.start)).only_enforce_if(active.Not())
        interval=model.new_optional_interval_var(ps,duration,pe,active,'possession_'+w.id)
        for s in w.sections: section_intervals.setdefault(s,[]).append(interval)
        members=[]
        for t in tasks:
            if incompatibility(t,w,snapshot): continue
            x=model.new_bool_var(t.id+'_'+w.id); choices[t.id,w.id]=x; members.append((t,x))
            model.add(starts[t.id]>=ps+w.preparation).only_enforce_if(x); model.add(ends[t.id]+w.restoration<=pe).only_enforce_if(x)
            model.add(x<=active)
        if members: model.add(sum(x for _,x in members)>=active)
        else: model.add(active==0)
        for i,(t,x) in enumerate(members):
            for u,y in members[i+1:]:
                if t.work_class in u.incompatible or u.work_class in t.incompatible: model.add(x+y<=1)
        pk[w.id]=(active,ps,pe,duration)
    for t in tasks:
        model.add(sum(x for (tid,_),x in choices.items() if tid==t.id)==selected[t.id])
        for pred in t.predecessors:
            if pred not in selected: model.add(selected[t.id]==0)
            else:
                model.add(selected[t.id]<=selected[pred]); model.add(starts[t.id]>=ends[pred]).only_enforce_if(selected[t.id])
        commitment=locks.get(t.id) or forced.get(t.id)
        if commitment:
            x=choices.get((t.id,commitment['window_id']))
            if x is None: model.add(selected[t.id]==0)
            else: model.add(x==1)
            if commitment.get('start') is not None: model.add(starts[t.id]==commitment['start'])
    for r in snapshot.resources:
        if intervals[r.id]: model.add_cumulative(intervals[r.id],[1]*len(intervals[r.id]),r.capacity)
    for section,start,end in fixed_intervals(snapshot,lo,hi):
        section_intervals.setdefault(section,[]).append(model.new_fixed_size_interval_var(start,end-start,'protection_'+section+str(start)))
    for ivs in section_intervals.values():
        if ivs: model.add_no_overlap(ivs)
    service=sum(t.weight*selected[t.id] for t in tasks)
    objectives=[('service','max',service)]
    if baseline:
        changes=[]; shifts=[]
        for a in baseline['assignments']:
            tid=a['task_id']
            if tid not in selected: continue
            same_time=model.new_bool_var('same_time_'+tid)
            model.add(starts[tid]==a['start']).only_enforce_if(same_time); model.add(starts[tid]!=a['start']).only_enforce_if(same_time.Not())
            same=model.new_bool_var('same_'+tid); x=choices.get((tid,a['window_id']))
            if x is None: model.add(same==0)
            else:
                model.add(same<=same_time); model.add(same<=x); model.add(same>=same_time+x-1)
            changes.append(1-same)
            diff=model.new_int_var(0,hi+abs(a['start']),'shift_'+tid); absolute=model.new_int_var(0,hi+abs(a['start']),'abs_'+tid)
            model.add_abs_equality(absolute,starts[tid]-a['start']); model.add(diff==absolute).only_enforce_if(selected[tid]); model.add(diff==0).only_enforce_if(selected[tid].Not()); shifts.append(diff)
        objectives.extend([('changed_assignments','min',sum(changes)),('start_shift','min',sum(shifts))])
    objectives.extend([('closed_section_minutes','min',sum(pk[w.id][3]*len(w.sections) for w in windows)),('tie_break','min',sum(starts.values())+sum(v[1] for v in pk.values()))])
    solver=cp_model.CpSolver(); solver.parameters.num_search_workers=1; solver.parameters.random_seed=snapshot.seed
    stages=[]; outcome='UNKNOWN'; candidate=None
    for name,direction,expr in objectives:
        remaining=limit-(time.perf_counter()-begun)
        if remaining<=0: break
        solver.parameters.max_time_in_seconds=remaining
        if direction=='max': model.maximize(expr)
        else: model.minimize(expr)
        status=solver.solve(model); outcome=solver.status_name(status)
        stages.append(dict(name=name,status=outcome,value=solver.objective_value if status in [cp_model.OPTIMAL,cp_model.FEASIBLE] else None,bound=solver.best_objective_bound))
        if status not in [cp_model.OPTIMAL,cp_model.FEASIBLE]: break
        assignments=[dict(task_id=tid,window_id=wid,start=solver.value(starts[tid]),end=solver.value(ends[tid])) for (tid,wid),x in choices.items() if solver.value(x)]
        packages=[dict(id='PK-'+w.id,window_id=w.id,sections=w.sections,start=solver.value(pk[w.id][1]),end=solver.value(pk[w.id][2]),preparation_end=solver.value(pk[w.id][1])+w.preparation,restoration_start=solver.value(pk[w.id][2])-w.restoration,window_start=w.start,window_end=w.end,margin=w.end-solver.value(pk[w.id][2]),task_ids=[a['task_id'] for a in assignments if a['window_id']==w.id]) for w in windows if solver.value(pk[w.id][0])]
        candidate=(assignments,packages)
        model.add(expr==round(solver.objective_value))
        if status==cp_model.FEASIBLE: break
    if candidate:
        outcome='OPTIMAL' if len(stages)==len(objectives) and all(s['status']=='OPTIMAL' for s in stages) else 'FEASIBLE'
    plan=dict(id=str(uuid4()),snapshot_id=snapshot.id,parent_id=(baseline or {}).get('id'),horizon=horizon,day=day,created_at=utcnow(),rule_version=snapshot.rule_version,solver_status=outcome,objective_stages=stages,runtime_seconds=round(time.perf_counter()-begun,4),instance=dict(tasks=len(tasks),windows=len(windows),assignment_candidates=len(choices)),assignments=candidate[0] if candidate else [],packages=candidate[1] if candidate else [],approval='proposed',core_only=core_only)
    assigned={a['task_id'] for a in plan['assignments']}
    plan['unscheduled']=[dict(task_id=t.id,mandatory=t.mandatory,due=t.due,deferrals=t.deferrals,reason=('Core-only proposal; optional work available for opportunity review' if core_only and not t.mandatory else 'Unverified asset: confirm mapping' if not t.verified else 'Materials not ready' if not t.ready else 'Overdue modeled deadline' if t.due<lo else 'No compatible window, resources, or retained service fit')) for t in tasks if t.id not in assigned]
    plan['validation']=validate(snapshot,plan,locks)
    plan['metrics']=metrics(snapshot,plan,baseline)
    return plan
