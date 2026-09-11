from .domain import Task, Window, Snapshot


def incompatibility(task: Task, window: Window, snapshot: Snapshot):
    if not task.verified: return 'Unverified asset: confirm location mapping'
    asset=next((a for a in snapshot.assets if a['id']==task.asset_id),None)
    if not asset or not asset['verified'] or asset['section']!=task.section or asset['line']!=task.line or asset['chainage_m']!=task.chainage_m:
        return 'Asset and canonical section/line/chainage do not match'
    if not task.ready: return 'Materials not ready'
    if task.section not in window.sections: return 'Incompatible footprint: directed section not covered'
    if not set(task.access)<=set(window.access): return 'Missing traffic protection or electrical access'
    if not set(task.isolation)<=set(window.isolation): return 'Incorrect isolation group'
    if task.earliest+task.duration+window.restoration>window.end or task.due<window.start+window.preparation+task.duration:
        return 'Eligibility/deadline violation'
    if task.duration+window.preparation+window.restoration>window.end-window.start: return 'Insufficient window'
    if not set(task.resources)<= {r.id for r in snapshot.resources}: return 'Unknown resource'
    return None


def eligible(snapshot, day, horizon):
    return [t for t in snapshot.tasks if t.earliest<(day+horizon)*1440 and (t.due>=day*1440 or t.mandatory or t.due<0)]
