from datetime import datetime
from .domain import Task


def canonicalize(row,source,snapshot):
    if not row.get('source_record_id'): raise ValueError('source_record_id is required')
    unit=row.get('chainage_unit')
    if unit not in ['m','km']: raise ValueError('Explicit chainage_unit must be m or km')
    chainage=float(row['chainage']); meters=chainage*(1000 if unit=='km' else 1)
    if not meters.is_integer(): raise ValueError('Chainage must resolve to integer meters')
    asset=next((a for a in snapshot.assets if a['id']==row.get('asset_id')),None)
    section=row.get('section',''); line=row.get('line','')
    if not any(s['id']==section and s['line']==line for s in snapshot.sections): raise ValueError('Unknown directed section / line')
    stamp=datetime.fromisoformat(row['source_timestamp'])
    if stamp.tzinfo is None: raise ValueError('source_timestamp must include timezone')
    anchor=datetime.fromisoformat(snapshot.anchor)
    def minute(field):
        value=datetime.fromisoformat(row[field])
        if value.tzinfo is None: raise ValueError(field+' must include timezone')
        return int((value-anchor).total_seconds()//60)
    def boolean(value):
        if str(value).lower() not in ['true','false','1','0']: raise ValueError('Boolean must be true or false')
        return str(value).lower() in ['true','1']
    verified=bool(asset and asset['verified'] and asset['section']==section and asset['line']==line and asset['chainage_m']==int(meters))
    resources=row.get('resources',[])
    if isinstance(resources,str): resources=resources.split('|')
    if not resources or not set(resources)<={r.id for r in snapshot.resources}: raise ValueError('Unknown or missing resources')
    isolation=row.get('isolation',[])
    if isinstance(isolation,str): isolation=[x for x in isolation.split('|') if x]
    access=row.get('access',['traffic'])
    if isinstance(access,str): access=access.split('|')
    if not set(access)<={'traffic','electrical'}: raise ValueError('Unsupported access type')
    task=Task(id=source+'-'+str(row['source_record_id']),source=source,source_record_id=str(row['source_record_id']),source_timestamp=stamp.isoformat(),department=row['department'],asset_id=row.get('asset_id','unresolved'),section=section,line=line,chainage_m=int(meters),title=row['title'],duration=int(row['duration']),earliest=minute('earliest'),due=minute('due'),mandatory=boolean(row.get('mandatory','false')),resources=resources,isolation=isolation,access=access,verified=verified,remarks=row.get('remarks',''))
    return task
