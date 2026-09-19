"""Username aliases, never public email lookups or a second password store."""
import hashlib
import re
import time
from collections import OrderedDict

import httpx
from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from .administration import AuthAdmin
from .domain import utcnow
from .persistence import LoginName
from .security import principal

INVALID_LOGIN = 'Invalid username or password.'
RESERVED = {'admin', 'administrator', 'railblox', 'support', 'system', 'root', 'security'}


def normalize(value):
    value = value.strip().lower()
    if not re.fullmatch(r'[a-z][a-z0-9._-]{2,31}', value) or value in RESERVED:
        raise ValueError('Use 3–32 characters, starting with a letter: letters, numbers, dots, underscores or hyphens. Reserved names cannot be used.')
    return value


class UsernameChange(BaseModel):
    model_config = ConfigDict(extra='forbid')
    username: str = Field(min_length=3, max_length=64)
    expected_username: str | None = None


class UsernameLogin(BaseModel):
    model_config = ConfigDict(extra='forbid')
    username: str = Field(min_length=1, max_length=64)
    password: SecretStr = Field(min_length=1, max_length=1024)


def install_usernames(app, settings, store):
    # Process-local, bounded and independent of the authenticated API limiter.
    # Deployment still requires a single API owner. Edge limiting is also advised.
    attempts = OrderedDict()

    def limit(key, maximum):
        now = time.monotonic()
        start, count = attempts.pop(key, (now, 0))
        if now - start >= 60:
            start, count = now, 0
        attempts[key] = (start, count + 1)
        if len(attempts) > 10000:
            attempts.popitem(last=False)
        if count >= maximum:
            raise HTTPException(429, 'Too many sign-in attempts. Wait one minute before retrying.', headers={'Retry-After': '60'})

    def configured():
        if settings.auth_mode != 'supabase' or not settings.supabase_service_role_key:
            raise HTTPException(503, 'Username sign-in is not configured. Use your work email or contact your administrator.')

    @app.get('/api/auth/username')
    def current_username():
        with store.session() as session:
            row = session.get(LoginName, principal.get()['id'])
            return {'username': row.username if row else None,
                    'enabled': settings.auth_mode == 'supabase' and bool(settings.supabase_service_role_key)}

    @app.patch('/api/auth/username')
    def change_username(body: UsernameChange):
        configured()
        who = principal.get()
        if not who.get('email_confirmed'):
            raise HTTPException(403, 'Confirm your work email before choosing a username.')
        try:
            username = normalize(body.username)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        with store.session() as session:
            row = session.get(LoginName, who['id'])
            previous = row.username if row else None
            if previous != body.expected_username:
                raise HTTPException(409, 'Your username changed. Reload the profile before saving again.')
            if previous == username:
                return {'username': username, 'enabled': True}
            try:
                if row:
                    changed = session.execute(update(LoginName).where(LoginName.user_id == who['id'],
                        LoginName.username == body.expected_username).values(username=username, updated_at=utcnow()))
                    if changed.rowcount != 1:
                        raise HTTPException(409, 'Your username changed. Reload the profile before saving again.')
                else:
                    session.add(LoginName(user_id=who['id'], username=username, updated_at=utcnow()))
                session.commit()
            except IntegrityError:
                session.rollback()
                raise HTTPException(409, 'That username is unavailable. Choose another name or reload your profile.') from None
        store.audit('username-updated', who['id'], {})
        return {'username': username, 'enabled': True}

    @app.post('/api/auth/username-login')
    async def username_login(request: Request):
        # Never trust caller-supplied forwarding headers for the limiter key.
        limit('ip:' + (request.client.host if request.client else 'unknown'), 20)
        configured()
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > 4096:
                raise HTTPException(413, 'Sign-in request is too large.')
        try:
            body = UsernameLogin.model_validate_json(bytes(raw))
            username = normalize(body.username)
        except (ValidationError, ValueError):
            raise HTTPException(401, INVALID_LOGIN) from None
        limit('name:' + hashlib.sha256(username.encode()).hexdigest(), 8)
        with store.session() as session:
            row = session.scalar(select(LoginName).where(LoginName.username == username))
            user_id = row.user_id if row else None
        # Fetch the provider's CURRENT email so email changes never break aliases
        # or let a recycled email authenticate the wrong account.
        email = 'unassigned-railblox-login@invalid.invalid'
        if user_id:
            try:
                user = await AuthAdmin(settings).request('GET', '/admin/users/' + user_id)
            except HTTPException as exc:
                if exc.status_code == 404:
                    raise HTTPException(401, INVALID_LOGIN) from None
                raise HTTPException(503, 'Sign-in service unavailable. Retry or use your work email.') from None
            if user.get('id') != user_id or not (user.get('email_confirmed_at') or user.get('confirmed_at')) or not user.get('email'):
                raise HTTPException(401, INVALID_LOGIN)
            email = user['email']
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
                response = await client.post(settings.supabase_url + '/auth/v1/token?grant_type=password',
                    headers={'apikey': settings.supabase_key},
                    json={'email': email, 'password': body.password.get_secret_value()})
        except httpx.HTTPError:
            raise HTTPException(503, 'Sign-in service unavailable. Retry or use your work email.') from None
        if response.status_code == 429:
            raise HTTPException(429, 'Too many sign-in attempts. Wait before retrying.')
        if response.status_code >= 500:
            raise HTTPException(503, 'Sign-in service unavailable. Retry or use your work email.')
        if response.status_code != 200:
            raise HTTPException(401, INVALID_LOGIN)
        try:
            data = response.json()
            if not user_id or data['user']['id'] != user_id or not all(isinstance(data.get(k), str) and data[k] for k in ('access_token', 'refresh_token')):
                raise ValueError()
        except (ValueError, KeyError, TypeError):
            raise HTTPException(401, INVALID_LOGIN) from None
        # Credentials and sessions are never logged, persisted, or audited.
        # The browser installs this provider session; /auth/me still verifies
        # identity, division, pending access and MFA on every protected request.
        return {'access_token': data['access_token'], 'refresh_token': data['refresh_token']}
