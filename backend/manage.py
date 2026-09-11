"""Fixture exports and explicit non-destructive workspace rebase."""
import argparse
import csv
import io
import json
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
from app.fixtures import acceptance, presentation
from app.domain import utcnow
from app.persistence import Store


def samples():
    root=Path(__file__).resolve().parent.parent/'sample_data'; root.mkdir(exist_ok=True)
    for fixture in [acceptance,presentation]:
        snapshot=fixture(); (root/(snapshot.corridor+'.json')).write_text(snapshot.model_dump_json(indent=2),encoding='utf-8')
    for source,dept in [('ROAMS','ENG'),('TMS','ENG'),('SMMS','S&T'),('TDMS','TRD'),('COA','ENG'),('BDMS','ENG')]:
        row=dict(source_record_id=source+'-001',asset_id='AS-S2-UP',section='S2-UP',line='UP',chainage='12.5',chainage_unit='km',department=dept,title=source+' illustrative inspection',duration=20,earliest='2026-09-10T07:30:00+05:30',due='2026-09-10T09:30:00+05:30',source_timestamp='2026-09-09T12:00:00Z',resources=dept+'-1',mandatory='false',isolation='ISO-2',access='traffic',remarks='Illustrative synthetic schema; not a production system interface.')
        (root/(source+'.json')).write_text(json.dumps([row],indent=2),encoding='utf-8')
        output=io.StringIO(newline=''); writer=csv.DictWriter(output,fieldnames=list(row)); writer.writeheader(); writer.writerow(row); (root/(source+'.csv')).write_text(output.getvalue(),encoding='utf-8')


def rebase(corridor,anchor,confirmed):
    if not confirmed: raise SystemExit('Pass --confirm to explicitly create a new rebased snapshot. Existing records are preserved.')
    stamp=datetime.fromisoformat(anchor)
    if stamp.tzinfo is None: raise SystemExit('Anchor must include timezone')
    store=Store(); store.init(); old=store.heads()[corridor]; snapshot=store.snapshot(old)
    snapshot.parent_id=old; snapshot.id=str(uuid4()); snapshot.anchor=stamp.astimezone(timezone.utc).isoformat(); snapshot.created_at=utcnow()
    store.save_snapshot(snapshot,head=True,expected=old); store.audit('rebase',snapshot.id,dict(previous=old,anchor=snapshot.anchor))
    print('New snapshot:',snapshot.id,'All imported records preserved. Generate a new plan.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(); sub=parser.add_subparsers(dest='command',required=True); sub.add_parser('export-fixtures')
    p=sub.add_parser('rebase'); p.add_argument('--corridor',choices=['small','presentation'],required=True); p.add_argument('--anchor',required=True); p.add_argument('--confirm',action='store_true')
    args=parser.parse_args()
    if args.command=='export-fixtures': samples()
    else: rebase(args.corridor,args.anchor,args.confirm)
