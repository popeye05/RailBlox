"""Single-division deployment boundary. Identity is verified by Supabase Auth."""
import os
import time
import logging
from collections import OrderedDict
from contextvars import ContextVar
from dataclasses import dataclass
from urllib.parse import urlparse
import httpx
from fastapi import HTTPException
from starlette.responses import JSONResponse

principal = ContextVar('principal', default={'id': 'local-demo', 'role': 'admin', 'division': 'demo'})
request_context = ContextVar('request_context', default='background')
log = logging.getLogger('railblox.access')
ROLES = {'viewer': 0, 'planner': 1, 'officer': 2, 'admin': 3}


@dataclass(frozen=True)
class Settings:
    environment: str
    auth_mode: str
    supabase_url: str
    supabase_key: str
    division: str
    origins: tuple

    @classmethod
    def load(cls):
        from pathlib import Path
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parents[2] / '.env', override=False)
        settings = cls(os.getenv('APP_ENV', 'development'), os.getenv('AUTH_MODE', 'demo'),
                       os.getenv('SUPABASE_URL', '').rstrip('/'), os.getenv('SUPABASE_PUBLISHABLE_KEY', ''),
                       os.getenv('DEPLOYMENT_DIVISION', 'demo'),
                       tuple(x.strip() for x in os.getenv('CORS_ORIGINS', 'http://127.0.0.1:5173,http://localhost:5173').split(',') if x.strip()))
        if settings.auth_mode not in {'demo', 'supabase'} or settings.environment not in {'development', 'production'}:
            raise RuntimeError('Invalid APP_ENV or AUTH_MODE')
        auth_url = urlparse(settings.supabase_url)
        if settings.auth_mode == 'supabase' and (auth_url.scheme != 'https' or not auth_url.hostname or
                auth_url.username or auth_url.password or auth_url.query or auth_url.fragment or auth_url.path or not settings.supabase_key):
            raise RuntimeError('Supabase authentication requires HTTPS SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY')
        if settings.auth_mode == 'supabase' and not settings.supabase_key.startswith('sb_publishable_'):
            raise RuntimeError('Use a Supabase publishable key (sb_publishable_...), never a secret or service-role key')
        if os.getenv('AI_DATA_POLICY', 'disabled') not in {'disabled', 'synthetic', 'authorized'}:
            raise RuntimeError('Invalid AI_DATA_POLICY')
        try:
            if not 0 <= int(os.getenv('AI_DAILY_CALL_LIMIT', '50')) <= 10000:
                raise ValueError()
        except ValueError:
            raise RuntimeError('AI_DAILY_CALL_LIMIT must be an integer from 0 to 10000') from None
        if settings.environment == 'production':
            if settings.auth_mode != 'supabase' or settings.division == 'demo' or not settings.division:
                raise RuntimeError('Production requires Supabase authentication and an explicit DEPLOYMENT_DIVISION')
            if not settings.origins or any(urlparse(x).scheme != 'https' or '*' in x for x in settings.origins):
                raise RuntimeError('Production requires explicit HTTPS CORS_ORIGINS')
            database = os.getenv('DATABASE_URL', '')
            from sqlalchemy.engine import make_url
            try:
                database_url = make_url(database)
            except Exception:
                raise RuntimeError('Production requires a valid PostgreSQL DATABASE_URL') from None
            if database_url.drivername != 'postgresql+psycopg' or database_url.query.get('sslmode') != 'verify-full':
                raise RuntimeError('Production requires PostgreSQL DATABASE_URL with sslmode=verify-full')
            if database_url.port == 6543:
                raise RuntimeError('Use a direct or session-pooler connection; transaction pooling cannot hold the deployment lock')
        return settings


async def verify_user(token, settings):
    # Auth validates the token and returns current administrator-controlled metadata.
    # No unverified JWT decoding, no user_metadata roles, no service-role key required.
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=False) as client:
            response = await client.get(settings.supabase_url + '/auth/v1/user', headers={
                'apikey': settings.supabase_key, 'Authorization': 'Bearer ' + token})
        if response.status_code in (401, 403):
            raise HTTPException(401, 'Session expired or invalid. Sign in again.')
        if response.status_code != 200:
            raise HTTPException(503, 'Identity service unavailable. Access is temporarily closed.')
        user = response.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(503, 'Identity service unavailable. Access is temporarily closed.')
    metadata = user.get('app_metadata', {})
    role = metadata.get('railblox_role')
    if not user.get('id') or role not in ROLES or metadata.get('railblox_division') != settings.division:
        raise HTTPException(403, 'An administrator must grant access to this division.')
    return {'id': user['id'], 'role': role, 'division': settings.division}


def required_role(method, path):
    path = path.rstrip('/')
    if path.startswith('/api/admin/'):
        return 'admin'
    if method in {'GET', 'HEAD', 'OPTIONS'}:
        return 'viewer'
    if path.endswith(('/approve', '/decision', '/review', '/outcomes', '/revise', '/finalize')):
        return 'officer'
    return 'planner'


def install_security(app, settings, store):
    # Bounded process-local limiter; production serves exactly one API process.
    buckets = OrderedDict()

    @app.middleware('http')
    async def access(request, call_next):
        from uuid import uuid4
        request_id = str(uuid4())
        request.state.request_id = request_id
        rid_token = request_context.set(request_id)
        who_token = None
        started = time.monotonic()
        try:
            path = request.url.path
            if path.startswith('/api/') and path != '/api/auth/config' and request.method != 'OPTIONS':
                if settings.auth_mode == 'supabase':
                    header = request.headers.get('authorization', '')
                    if not header.startswith('Bearer ') or len(header) > 16384:
                        raise HTTPException(401, 'Sign in to access this workspace.')
                    who = await verify_user(header[7:], settings)
                else:
                    who = {'id': 'local-demo', 'role': 'admin', 'division': settings.division}
                who_token = principal.set(who)
                if ROLES[who['role']] < ROLES[required_role(request.method, path)]:
                    raise HTTPException(403, 'Your role does not permit this action.')
                key = who['id']
                now = time.monotonic()
                window, count = buckets.pop(key, (now, 0))
                if now - window >= 60:
                    window, count = now, 0
                buckets[key] = (window, count + 1)
                if len(buckets) > 10000:
                    buckets.popitem(last=False)
                if count >= 240:
                    raise HTTPException(429, 'Request limit reached. Retry in one minute.')
                length = request.headers.get('content-length')
                if length and (not length.isdigit() or int(length) > 6 * 1024 * 1024):
                    raise HTTPException(413, 'Request body exceeds 6 MB.')
            response = await call_next(request)
        except HTTPException as exc:
            response = JSONResponse(status_code=exc.status_code, content={
                'code': 'ACCESS_REJECTED', 'message': exc.detail, 'request_id': request_id})
        finally:
            if who_token is not None:
                principal.reset(who_token)
            request_context.reset(rid_token)
        response.headers.update({'X-Request-ID': request_id, 'X-Content-Type-Options': 'nosniff',
                                 'Referrer-Policy': 'no-referrer', 'Cache-Control': 'no-store'})
        if settings.environment == 'production':
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        # No request bodies, tokens, query strings, or upstream responses in logs.
        log.info('request_id=%s method=%s status=%s duration_ms=%d', request_id, request.method,
                 response.status_code, (time.monotonic() - started) * 1000)
        return response

    @app.get('/api/auth/config')
    def auth_config():
        return {'mode': settings.auth_mode, 'supabase_url': settings.supabase_url,
                'publishable_key': settings.supabase_key if settings.auth_mode == 'supabase' else '',
                'division': settings.division}

    @app.get('/api/auth/me')
    def me():
        return principal.get()

    @app.get('/api/admin/audit')
    def audit(limit: int = 100):
        return store.events()[-min(max(limit, 1), 500):]
