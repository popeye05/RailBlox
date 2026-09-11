"""Operator-only first-admin bootstrap. Run on the backend host, never in a browser."""
import argparse
import asyncio
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import text
from .administration import AuthAdmin, metadata_dict
from .security import Settings, principal
from .persistence import Store


async def bootstrap(settings, user_id, expected_email, apply=False):
    service = AuthAdmin(settings)
    # Enumerate every page; never infer 'no admins' from the first page only.
    for page in range(1, 1001):
        users = await service.users(page, 100)
        if any(metadata_dict(u).get('railblox_role') == 'admin' and
               metadata_dict(u).get('railblox_division') == settings.division for u in users):
            raise ValueError('An administrator already exists. Use Admin > User access instead.')
        if len(users) < 100:
            break
    else:
        raise ValueError('User enumeration limit reached. Bootstrap stopped without granting access.')
    user = await service.request('GET', '/admin/users/' + str(user_id))
    if user.get('email', '').casefold() != expected_email.casefold():
        raise ValueError('Email does not match the supplied user ID.')
    if not (user.get('email_confirmed_at') or user.get('confirmed_at')):
        raise ValueError('Confirm this account email before bootstrap.')
    metadata = dict(metadata_dict(user))
    if metadata.get('railblox_division') not in (None, settings.division):
        raise ValueError('Account is assigned to another division.')
    if not apply:
        return f'Review: grant admin to account {user_id} in {settings.division}. Run again with --apply to save.'
    store = Store()
    token = principal.set({'id': 'operator-bootstrap', 'role': 'admin', 'division': settings.division})
    lease = None
    try:
        if settings.environment == 'production':
            lease = store.engine.connect()
            if not lease.execute(text('SELECT pg_try_advisory_lock(724196310)')).scalar():
                raise ValueError('Stop the API process before bootstrap so the deployment lock is exclusive.')
        # Recheck provider state while holding the deployment lease. This also
        # refreshes the target metadata before a second operator could grant access.
        await bootstrap(settings, user_id, expected_email, apply=False)
        user = await service.request('GET', '/admin/users/' + str(user_id))
        metadata = dict(metadata_dict(user))
        store.init()
        store.audit('admin-bootstrap-requested', str(user_id), {})
        metadata.update(railblox_role='admin', railblox_division=settings.division)
        updated = await service.request('PUT', '/admin/users/' + str(user_id), {'app_metadata': metadata})
        actual = metadata_dict(updated)
        if (actual.get('railblox_role'), actual.get('railblox_division')) != ('admin', settings.division):
            raise ValueError('Bootstrap response did not confirm access. Inspect the account before retrying.')
        store.audit('admin-bootstrap-completed', str(user_id), {})
    finally:
        if lease is not None:
            lease.execute(text('SELECT pg_advisory_unlock(724196310)')); lease.close()
        principal.reset(token)
        store.engine.dispose()
    return 'First administrator configured. Sign in and assign a second administrator from User access.'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--user-id', type=UUID, required=True)
    parser.add_argument('--email', required=True, help='Expected email; verifies the account ID')
    parser.add_argument('--apply', action='store_true', help='Persist the reviewed grant')
    args = parser.parse_args()
    try:
        print(asyncio.run(bootstrap(Settings.load(), args.user_id, args.email, args.apply)))
    except (HTTPException, ValueError, RuntimeError) as exc:
        parser.exit(1, (str(exc.detail) if isinstance(exc, HTTPException) else str(exc)) + '\n')


if __name__ == '__main__':
    main()
