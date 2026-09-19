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
from .permissions import ROLES, CAPABILITIES, PUBLIC_AUTH_ROUTES, capabilities, required_role

principal = ContextVar('principal', default={'id': 'local-demo', 'role': 'admin', 'division': 'demo'})
request_context = ContextVar('request_context', default='background')
log = logging.getLogger('railblox.access')


def profile_text(value, maximum=120):
    return value[:maximum] if isinstance(value, str) else ''


@dataclass(frozen=True)
class Settings:
    environment: str
    auth_mode: str
    supabase_url: str
    supabase_key: str
    supabase_service_role_key: str
    division: str
    origins: tuple
    public_signup: bool = False
    collect_dob: bool = False
    require_mfa: bool = False
    request_limit: int = 240

    @classmethod
    def load(cls):
        from pathlib import Path
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parents[2] / '.env', override=False)
        settings = cls(os.getenv('APP_ENV', 'development'), os.getenv('AUTH_MODE', 'demo'),
                       os.getenv('SUPABASE_URL', '').rstrip('/'), os.getenv('SUPABASE_PUBLISHABLE_KEY', ''),
                       os.getenv('SUPABASE_SERVICE_ROLE_KEY', ''),
                       os.getenv('DEPLOYMENT_DIVISION', 'demo'),
                       tuple(x.strip() for x in os.getenv('CORS_ORIGINS', 'http://127.0.0.1:5173,http://localhost:5173').split(',') if x.strip()),
                       os.getenv('PUBLIC_SIGNUP_ENABLED', 'false' if os.getenv('APP_ENV') == 'production' else 'true').lower() == 'true',
                       os.getenv('COLLECT_DATE_OF_BIRTH', 'false' if os.getenv('APP_ENV') == 'production' else 'true').lower() == 'true',
                       os.getenv('REQUIRE_MFA', 'true' if os.getenv('APP_ENV') == 'production' else 'false').lower() == 'true',
                       int(os.getenv('API_RATE_LIMIT_PER_MINUTE', '240')))
        if os.getenv('REQUIRE_MFA', 'true').lower() not in {'true', 'false'}:
            raise RuntimeError('REQUIRE_MFA must be true or false')
        if settings.environment == 'production' and not settings.require_mfa:
            log.warning('MFA enforcement is disabled for testing. Restore REQUIRE_MFA=true before operational use.')
        if not 1 <= settings.request_limit <= 10000:
            raise RuntimeError('API_RATE_LIMIT_PER_MINUTE must be between 1 and 10000')
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
            if not settings.origins or any(urlparse(x).scheme != 'https' or not urlparse(x).hostname or
                    urlparse(x).username or urlparse(x).password or urlparse(x).path or urlparse(x).query or
                    urlparse(x).fragment or '*' in x for x in settings.origins):
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


async def verify_user(token, settings, allow_pending=False):
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
    if not isinstance(user, dict):
        raise HTTPException(503, 'Identity service returned an invalid response.')
    metadata = user.get('app_metadata') or {}
    if not isinstance(metadata, dict):
        raise HTTPException(503, 'Identity service returned invalid access metadata.')
    role = metadata.get('railblox_role')
    if not user.get('id'):
        raise HTTPException(401, 'Invalid identity response.')
    granted = role in ROLES and metadata.get('railblox_division') == settings.division
    if not granted and not allow_pending:
        raise HTTPException(403, 'An administrator must grant access to this division.')
    # This exact bearer token has already been authenticated by /auth/v1/user.
    # Read its assurance claim only AFTER that verification, never to grant a role.
    import base64
    import json
    aal = 'aal1'
    try:
        encoded = token.split('.')[1]
        claims = json.loads(base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4)))
        if claims.get('sub') == user['id'] and claims.get('aal') == 'aal2':
            aal = 'aal2'
    except (ValueError, IndexError, TypeError, AttributeError):
        pass
    profile = user.get('user_metadata') or {}
    if not isinstance(profile, dict):
        profile = {}
    return {'id': user['id'], 'email': user.get('email', ''),
            'name': profile_text(profile.get('full_name')),
            'designation': profile_text(profile.get('designation'), 80),
            'department': profile_text(profile.get('department'), 80),
            'location': profile_text(profile.get('location'), 100),
            'created_at': profile_text(user.get('created_at'), 40),
            'last_sign_in_at': profile_text(user.get('last_sign_in_at'), 40),
            'email_confirmed': bool(user.get('email_confirmed_at') or user.get('confirmed_at')),
            **({'date_of_birth': profile_text(profile.get('date_of_birth'), 10)} if settings.collect_dob else {}),
            'role': role if granted else None, 'division': settings.division,
            'access_pending': not granted, 'aal': aal,
            'mfa_policy_enabled': settings.require_mfa,
            'mfa_required': settings.require_mfa and granted and role != 'viewer'}


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
            public_login = (request.method, path.rstrip('/')) in PUBLIC_AUTH_ROUTES
            if path.startswith('/api/') and path != '/api/auth/config' and not public_login and request.method != 'OPTIONS':
                if settings.auth_mode == 'supabase':
                    header = request.headers.get('authorization', '')
                    if not header.startswith('Bearer ') or len(header) > 16384:
                        raise HTTPException(401, 'Sign in to access this workspace.')
                    who = await verify_user(header[7:], settings, allow_pending=path == '/api/auth/me')
                else:
                    who = {'id': 'local-demo', 'role': 'admin', 'division': settings.division}
                who_token = principal.set(who)
                if path != '/api/auth/me':
                    if who.get('mfa_required') and who.get('aal') != 'aal2':
                        raise HTTPException(403, 'Multi-factor verification is required. Verify your authenticator to continue.')
                    needed = required_role(request.method, path)
                    if needed is None:
                        raise HTTPException(403, 'This action has no assigned access policy.')
                    if ROLES.get(who['role'], -1) < ROLES[needed]:
                        raise HTTPException(403, f'{needed.title()} access or higher is required for this action.')
                key = who['id']
                now = time.monotonic()
                window, count = buckets.pop(key, (now, 0))
                if now - window >= 60:
                    window, count = now, 0
                buckets[key] = (window, count + 1)
                if len(buckets) > 10000:
                    buckets.popitem(last=False)
                if count >= settings.request_limit:
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
                'division': settings.division, 'public_signup_enabled': settings.public_signup,
                'collect_date_of_birth': settings.collect_dob, 'require_mfa': settings.require_mfa}

    @app.get('/api/auth/me')
    def me():
        return principal.get()

    @app.get('/api/auth/permissions')
    def permissions():
        return {'roles': list(ROLES), 'capabilities': CAPABILITIES,
                'granted': capabilities(principal.get()['role'])}

    @app.get('/api/auth/activity')
    def activity():
        from sqlalchemy import select
        from .persistence import Audit
        who = principal.get()
        with store.session() as session:
            rows = session.scalars(select(Audit).where(
                Audit.data['actor'].as_string() == who['id'],
                Audit.data['division'].as_string() == who['division']
            ).order_by(Audit.at.desc(), Audit.id.desc()).limit(20))
            return [{'id': row.id, 'at': row.at, 'action': row.kind,
                     'record_id': row.record_id} for row in rows]

    @app.get('/api/status')
    def status():
        import hashlib
        import json
        from sqlalchemy import select, func
        from .persistence import Document
        latest = store.events(limit=1)
        with store.session() as session:
            documents = session.scalar(select(func.count()).select_from(Document))
        revision = hashlib.sha256(json.dumps([store.heads(), latest[0]['id'] if latest else None, documents], sort_keys=True).encode()).hexdigest()[:20]
        return {'revision': revision, 'updates': 'Authenticated polling every 30 seconds',
                'realtime': 'SSE and Supabase Realtime not configured',
                'source_connections': 'Live railway and weather connectors not configured; imported or synthetic snapshots only',
                'external_ai': 'Enabled' if os.getenv('AI_DATA_POLICY') in {'synthetic', 'authorized'} and os.getenv('OPENAI_API_KEY') and os.getenv('OPENAI_MODEL') else 'Disabled',
                'user_administration': bool(settings.supabase_service_role_key),
                'mfa_enforced': settings.require_mfa,
                'public_signup': settings.public_signup,
                'database': 'PostgreSQL' if store.engine.dialect.name == 'postgresql' else 'SQLite'}

    from .administration import install_administration
    install_administration(app, settings, store)
    from .usernames import install_usernames
    install_usernames(app, settings, store)
