import os
from uuid import uuid4
from sqlalchemy import create_engine, String, JSON, ForeignKey, select, update, event, CheckConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session
from .domain import Snapshot, utcnow


class Base(DeclarativeBase): pass


class SnapshotRow(Base):
    __tablename__='snapshots'
    id: Mapped[str]=mapped_column(String,primary_key=True)
    corridor: Mapped[str]=mapped_column(String,index=True)
    meta: Mapped[dict]=mapped_column(JSON)


class EntityRow(Base):
    __tablename__='snapshot_entities'
    snapshot_id: Mapped[str]=mapped_column(ForeignKey('snapshots.id'),primary_key=True)
    kind: Mapped[str]=mapped_column(String,primary_key=True)
    id: Mapped[str]=mapped_column(String,primary_key=True)
    data: Mapped[dict]=mapped_column(JSON)


class Document(Base):
    __tablename__='documents'
    id: Mapped[str]=mapped_column(String,primary_key=True)
    kind: Mapped[str]=mapped_column(String,index=True)
    data: Mapped[dict]=mapped_column(JSON)


class Head(Base):
    __tablename__='workspace_heads'
    id: Mapped[str]=mapped_column(String,primary_key=True)
    snapshot_id: Mapped[str]=mapped_column(ForeignKey('snapshots.id'))


class Audit(Base):
    __tablename__='audit_events'
    id: Mapped[str]=mapped_column(String,primary_key=True)
    at: Mapped[str]=mapped_column(String)
    kind: Mapped[str]=mapped_column(String)
    record_id: Mapped[str]=mapped_column(String,index=True)
    data: Mapped[dict]=mapped_column(JSON)


class LoginName(Base):
    __tablename__ = 'login_names'
    __table_args__ = (CheckConstraint('username = lower(username)', name='ck_login_names_lowercase'),)
    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)


class Store:
    def __init__(self,url=None):
        url=url or os.getenv('DATABASE_URL','sqlite:///./railblox.db')
        self.private_schema = not url.startswith('sqlite') and os.getenv('APP_ENV') == 'production'
        connect_args = {'check_same_thread':False,'timeout':30} if url.startswith('sqlite') else ({'options':'-csearch_path=railblox'} if self.private_schema else {})
        self.engine=create_engine(url,pool_pre_ping=True,connect_args=connect_args)
        if url.startswith('sqlite'):
            @event.listens_for(self.engine,'connect')
            def configure(conn,_):
                conn.execute('PRAGMA foreign_keys=ON'); conn.execute('PRAGMA journal_mode=WAL')

    def session(self): return Session(self.engine,expire_on_commit=False)

    def init(self):
        if self.private_schema:
            from sqlalchemy import text
            with self.engine.begin() as connection:
                if not connection.execute(text("SELECT to_regnamespace('railblox')")).scalar():
                    connection.execute(text('CREATE SCHEMA railblox'))
                connection.execute(text('REVOKE ALL ON SCHEMA railblox FROM PUBLIC'))
        from alembic.config import Config
        from alembic import command
        from pathlib import Path
        config=Config(); config.set_main_option('script_location',str(Path(__file__).resolve().parents[1]/'migrations'))
        with self.engine.begin() as connection:
            config.attributes['connection']=connection; command.upgrade(config,'head')
        with self.session() as s:
            for row in s.scalars(select(Document).where(Document.kind.in_(['run','automation_run','ai_call']))):
                if row.data['status'] in ['queued','running','started']:
                    row.data={**row.data,'status':'failed','completed_at':utcnow(),'error':'Backend restarted; review and retry this operation.'}
            s.commit()

    def save_snapshot(self,snapshot,head=False,expected=None):
        data=snapshot.model_dump(); kinds=['tasks','windows','resources','sections','assets','movements']
        with self.session() as s:
            if expected:
                result=s.execute(update(Head).where(Head.id==snapshot.corridor,Head.snapshot_id==expected).values(snapshot_id=expected))
                if not result.rowcount: raise ValueError('STALE_SNAPSHOT')
            s.add(SnapshotRow(id=snapshot.id,corridor=snapshot.corridor,meta={k:v for k,v in data.items() if k not in kinds})); s.flush()
            for kind in kinds:
                for item in data[kind]: s.add(EntityRow(snapshot_id=snapshot.id,kind=kind,id=item['id'],data=item))
            if head:
                h=s.get(Head,snapshot.corridor)
                if h: h.snapshot_id=snapshot.id
                else: s.add(Head(id=snapshot.corridor,snapshot_id=snapshot.id))
            s.commit()

    def snapshot(self,id):
        with self.session() as s:
            row=s.get(SnapshotRow,id)
            if not row: raise KeyError(id)
            data=dict(row.meta)
            for kind in ['tasks','windows','resources','sections','assets','movements']: data[kind]=[]
            for e in s.scalars(select(EntityRow).where(EntityRow.snapshot_id==id).order_by(EntityRow.id)): data[e.kind].append(e.data)
            return Snapshot.model_validate(data)

    def heads(self):
        with self.session() as s: return {h.id:h.snapshot_id for h in s.scalars(select(Head))}

    def put(self,kind,data,mutable=False):
        with self.session() as s:
            row=s.get(Document,data['id'])
            if row:
                if not mutable: raise ValueError('Immutable document already exists')
                row.data=data
            else: s.add(Document(id=data['id'],kind=kind,data=data))
            s.commit()
        return data

    def get(self,id,kind=None):
        with self.session() as s:
            row=s.get(Document,id)
            if not row or (kind and row.kind!=kind): raise KeyError(id)
            return row.data

    def all(self,kind):
        with self.session() as s: return [r.data for r in s.scalars(select(Document).where(Document.kind==kind))]

    def audit(self,kind,record_id,data,session=None):
        from .security import principal, request_context
        identity=principal.get()
        row=Audit(id=str(uuid4()),at=utcnow(),kind=kind,record_id=record_id,
                  data={**data,'actor':identity['id'],'role':identity['role'],'division':identity['division'],'request_id':request_context.get()})
        if session: session.add(row)
        else:
            with self.session() as s: s.add(row); s.commit()
        return row.id

    def events(self,id=None,limit=None):
        with self.session() as s:
            query=select(Audit).order_by(Audit.at.desc(), Audit.id.desc()) if limit else select(Audit).order_by(Audit.at, Audit.id)
            if id: query=query.where(Audit.record_id==id)
            if limit: query=query.limit(limit)
            rows=[dict(id=r.id,at=r.at,kind=r.kind,record_id=r.record_id,data=r.data) for r in s.scalars(query)]
            return list(reversed(rows)) if limit else rows
