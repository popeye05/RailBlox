from itertools import combinations
from .footprints import incompatibility
from .solver import solve


def discover(snapshot, plan, window_id, locks=None):
    window=next((w for w in snapshot.windows if w.id==window_id),None)
    package=next((p for p in plan['packages'] if p['window_id']==window_id),None)
    if not window or not package: raise ValueError('Choose an existing package')
    existing={a['task_id']:a for a in plan['assignments']}; possible=[]; records=[]
    for t in snapshot.tasks:
        if t.id in package['task_ids']: continue
        reason=incompatibility(t,window,snapshot)
        if reason:
            records.append(dict(task_ids=[t.id],accepted=False,reasons=[reason],window_id=window_id,snapshot_id=snapshot.id))
        else: possible.append(t)
    possible=sorted(possible,key=lambda t:(not t.mandatory,-t.weight,t.id))[:6]
    bundles=[c for size in [1,2,3] for c in combinations(possible,size)][:24]
    for bundle in bundles:
        ids=[t.id for t in bundle]
        # All other commitments stay fixed. A candidate already scheduled elsewhere
        # may be brought forward, but only under its actual eligibility constraints.
        fixed={k:v for k,v in existing.items() if k not in ids}; fixed.update(locks or {})
        forced={tid:dict(window_id=window_id) for tid in ids}
        trial=solve(snapshot,plan['horizon'],plan['day'],baseline=plan,locks=fixed,forced=forced,allowed=set(existing)|set(ids),seconds=0.4)
        ok=trial['solver_status'] in ['OPTIMAL','FEASIBLE'] and trial['validation']['valid']
        new=next((p for p in trial['packages'] if p['window_id']==window_id),None)
        reasons=[]
        if not ok:
            retained=[t for t in snapshot.tasks if t.id in package['task_ids']]+list(bundle)
            for i,t in enumerate(retained):
                for u in retained[i+1:]:
                    if t.work_class in u.incompatible or u.work_class in t.incompatible:
                        reasons.append(f'Incompatible work classes: {t.id} ({t.work_class}) and {u.id} ({u.work_class})')
            for resource in snapshot.resources:
                demand=sum(t.duration+resource.setup for t in retained if resource.id in t.resources)
                available=(window.end-window.start-window.preparation-window.restoration+resource.setup)*resource.capacity
                if demand>available: reasons.append(f'Resource conflict: {resource.id} requires {demand} crew-min including setup; package capacity is {available}')
            for t in bundle:
                after=max([window.start+window.preparation,t.earliest]+[existing[p]['end'] for p in t.predecessors if p in existing])
                if after+t.duration+window.restoration>window.end:
                    reasons.append(f'Insufficient window: {t.id} needs handback at minute {after+t.duration+window.restoration}; window ends at {window.end}')
            if not reasons: reasons.append(f'Complete-bundle solve {trial["solver_status"]}: no validated addition preserving the listed assignments and source calendars within this window')
        record=dict(task_ids=ids,accepted=ok,window_id=window_id,snapshot_id=snapshot.id,footprint=window.sections,resources=sorted({r for t in bundle for r in t.resources}),service_benefit=sum(t.weight for t in bundle if t.id not in existing),reasons=reasons,solver_status=trial['solver_status'])
        if ok:
            record.update(added_closed_section_minutes=trial['metrics']['closed_section_minutes']-plan['metrics']['closed_section_minutes'],margin_change=new['margin']-package['margin'],remaining_margin=new['margin'])
        records.append(record)
    return dict(window_id=window_id,package_id=package['id'],snapshot_id=snapshot.id,records=records,bounds=dict(footprint_candidates=6,bundles=24,seconds_per_solve=0.4))
