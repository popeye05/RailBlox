"""Division-scoped administration through Supabase's server-only API."""
import asyncio
from typing import Literal
from uuid import UUID, uuid4
import httpx
from fastapi import HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from .security import principal, profile_text, ROLES

Role = Literal['viewer', 'planner', 'officer', 'admin']


def metadata_dict(user):
    value = user.get('app_metadata') or {}
    return value if isinstance(value, dict) else {}


class AccessChange(BaseModel):
    model_config = ConfigDict(extra='forbid')
    role: Role | None
    expected_role: Role | None
    expected_division: str | None
    reason: str = Field(min_length=3, max_length=500)


class Invitation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    email: str = Field(min_length=3, max_length=254, pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    name: str = Field(min_length=1, max_length=120)
    requested_role: Role = 'viewer'


class AuthAdmin:
    def __init__(self, settings):
        self.settings = settings

    async def request(self, method, path, payload=None, params=None):
        key = self.settings.supabase_service_role_key
        if self.settings.auth_mode != 'supabase' or not key:
            raise HTTPException(503, 'User administration is not configured. Add SUPABASE_SERVICE_ROLE_KEY to the backend only.')
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
                response = await client.request(method, self.settings.supabase_url + '/auth/v1' + path,
                    json=payload, params=params, headers={'apikey': key, 'Authorization': 'Bearer ' + key})
        except httpx.HTTPError:
            raise HTTPException(503, 'Identity service unavailable. Refresh the user list before retrying a change.') from None
        if response.status_code == 429:
            raise HTTPException(429, 'Identity service rate limit reached. Wait before retrying.')
        if response.status_code == 404:
            raise HTTPException(404, 'User account was not found.')
        if not 200 <= response.status_code < 300:
            raise HTTPException(502, 'Identity service rejected the request. Check its Auth logs and email configuration.')
        try:
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError()
            return data
        except ValueError:
            raise HTTPException(502, 'Identity service returned an invalid response.') from None

    async def users(self, page=1, per_page=100):
        result = await self.request('GET', '/admin/users', params={'page': page, 'per_page': per_page})
        if not isinstance(result.get('users'), list):
            raise HTTPException(502, 'Identity service returned an invalid user list.')
        return result['users']


def user_view(user):
    metadata = metadata_dict(user)
    profile = user.get('user_metadata') or {}
    if not isinstance(profile, dict):
        profile = {}
    # Explicit allowlist: DOB, tokens and unrelated profile metadata never leave this API.
    requested = profile_text(profile.get('requested_role'))
    return dict(id=user['id'], email=user.get('email', ''), name=profile_text(profile.get('full_name')),
                requested_role=requested if requested in ROLES else 'viewer',
                role=metadata.get('railblox_role'), division=metadata.get('railblox_division'),
                confirmed_at=user.get('email_confirmed_at') or user.get('confirmed_at'),
                created_at=user.get('created_at'), last_sign_in_at=user.get('last_sign_in_at'))


def install_administration(app, settings, store):
    service = AuthAdmin(settings)
    lock = asyncio.Lock()  # Deployment permits one API process.

    @app.get('/api/admin/users')
    async def users(page: int = Query(1, ge=1), per_page: int = Query(50, ge=1, le=100)):
        records = await service.users(page, per_page)
        # Shared-project users assigned elsewhere are never administered here.
        visible = [user_view(u) for u in records
                   if metadata_dict(u).get('railblox_division') in (None, settings.division)]
        return dict(users=visible, page=page, has_more=len(records) == per_page)

    @app.patch('/api/admin/users/{user_id}')
    async def change_access(user_id: UUID, body: AccessChange):
        user_id = str(user_id)
        async with lock:
            actor = await service.request('GET', '/admin/users/' + principal.get()['id'])
            actor_metadata = metadata_dict(actor)
            if (actor_metadata.get('railblox_role'), actor_metadata.get('railblox_division')) != ('admin', settings.division):
                raise HTTPException(403, 'Your administrator access changed. Sign in again.')
            current = await service.request('GET', '/admin/users/' + user_id)
            metadata = dict(metadata_dict(current))
            before = metadata.get('railblox_role')
            division = metadata.get('railblox_division')
            if division not in (None, settings.division):
                raise HTTPException(403, 'This account belongs to another division.')
            if (before, division) != (body.expected_role, body.expected_division):
                raise HTTPException(409, 'Access changed since this page loaded. Refresh and review the new assignment.')
            if user_id == principal.get()['id'] and body.role != 'admin':
                raise HTTPException(409, 'Another administrator must change your access. Your own administrator access is protected.')
            if body.role and not (current.get('email_confirmed_at') or current.get('confirmed_at')):
                raise HTTPException(409, 'The user must confirm their email before access is assigned.')
            metadata.update(railblox_role=body.role, railblox_division=settings.division if body.role else None)
            # Supabase merges app_metadata. Explicit nulls revoke existing keys.
            operation = str(uuid4())
            details = dict(operation_id=operation, previous_role=before, assigned_role=body.role,
                           previous_division=division, reason=body.reason.strip())
            store.audit('user-access-requested', user_id, details)
            try:
                updated = await service.request('PUT', '/admin/users/' + user_id, {'app_metadata': metadata})
            except HTTPException:
                store.audit('user-access-unconfirmed', user_id, details)
                raise
            actual = metadata_dict(updated)
            if (actual.get('railblox_role'), actual.get('railblox_division')) != (body.role, metadata['railblox_division']):
                store.audit('user-access-unconfirmed', user_id, details)
                raise HTTPException(502, 'Access change could not be confirmed. Refresh before retrying.')
            store.audit('user-access-updated', user_id, details)
            return user_view(updated)

    @app.post('/api/admin/invitations')
    async def invite(body: Invitation):
        operation = str(uuid4())
        store.audit('user-invitation-requested', operation, {'requested_role': body.requested_role})
        try:
            # Invites establish identity only. A separate reviewed grant is required.
            result = await service.request('POST', '/invite', {'email': body.email.strip(),
                'data': {'full_name': body.name.strip(), 'requested_role': body.requested_role}})
        except HTTPException:
            store.audit('user-invitation-unconfirmed', operation, {})
            raise
        store.audit('user-invited', result.get('id', operation), {'operation_id': operation})
        return {'message': 'Invitation sent. After email confirmation, review and assign access.'}

    @app.get('/api/admin/audit')
    def audit(limit: int = Query(100, ge=1, le=500)):
        return store.events(limit=limit)
