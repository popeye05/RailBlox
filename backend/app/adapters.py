import csv
import io
import json
from uuid import uuid4
from .canonicalization import canonicalize
from .domain import utcnow

SOURCES=['ROAMS','TMS','SMMS','TDMS','COA','BDMS']
LIMIT=5*1024*1024


def preview(content,filename,source,snapshot):
    if source not in SOURCES: raise ValueError('Unsupported illustrative source')
    if len(content)>LIMIT: raise ValueError('Maximum upload size is 5 MB')
    decoded=content.decode('utf-8-sig')
    if filename.lower().endswith('.csv'): rows=list(csv.DictReader(io.StringIO(decoded)))
    elif filename.lower().endswith('.json'):
        rows=json.loads(decoded)
        if not isinstance(rows,list): raise ValueError('JSON must contain an array of records')
    else: raise ValueError('Only UTF-8 CSV and JSON files are supported')
    if len(rows)>5000: raise ValueError('Maximum 5,000 records per import')
    if not rows: raise ValueError('File contains no data records')
    result=[]; seen=set()
    for index,row in enumerate(rows):
        try:
            if not isinstance(row,dict): raise ValueError('Record must be an object')
            t=canonicalize(row,source,snapshot)
            if t.source_record_id in seen: raise ValueError('Duplicate source_record_id in this upload')
            seen.add(t.source_record_id)
            result.append(dict(row=index+1,raw=row,canonical=t.model_dump(),errors=[],mapping_required=not t.verified))
        except (ValueError,KeyError,TypeError) as exc: result.append(dict(row=index+1,raw=row,errors=[str(exc)]))
    return dict(id=str(uuid4()),snapshot_id=snapshot.id,source=source,filename=filename,created_at=utcnow(),rows=result,columns=list(rows[0]) if isinstance(rows[0],dict) else [],committed=False)


def safe_csv(rows):
    output=io.StringIO(newline='')
    if not rows: return ''
    def safe(v):
        value=json.dumps(v) if isinstance(v,(dict,list)) else str(v) if v is not None else ''
        return "'"+value if value.lstrip().startswith(('=','+','-','@','\t','\r')) else value
    writer=csv.DictWriter(output,fieldnames=list(rows[0])); writer.writeheader()
    writer.writerows({k:safe(v) for k,v in row.items()} for row in rows)
    return output.getvalue()
