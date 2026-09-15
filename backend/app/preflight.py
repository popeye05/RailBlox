"""Read-only deployment configuration check. Does not contact providers or alter accounts."""
import json
import os
from .security import Settings


def check():
    checks = []
    try:
        settings = Settings.load()
    except RuntimeError as exc:
        return {'ready': False, 'checks': [{'name': 'Configuration', 'ok': False, 'message': str(exc)}]}
    def add(name, ok, message):
        checks.append({'name': name, 'ok': bool(ok), 'message': message})
    add('Production mode', settings.environment == 'production', 'APP_ENV must be production for a hosted pilot.')
    add('Authenticated access', settings.auth_mode == 'supabase', 'Supabase must verify all workspace access.')
    add('MFA', settings.require_mfa, 'Operational roles require authenticator verification.')
    add('User administration', settings.supabase_service_role_key, 'Configure the server-only administration credential.')
    fields = [settings.supabase_url, settings.supabase_key, os.getenv('DATABASE_URL', ''), *settings.origins]
    add('Configuration placeholders', not any(marker in value.upper() for value in fields
        for marker in ['REPLACE_ME', 'YOUR-PROJECT', 'YOUR-APP', 'YOUR_APP']), 'Replace all example values with deployment configuration.')
    add('Invitation policy', not settings.public_signup, 'For the controlled pilot, disable public signup in both application and provider settings.')
    add('Profile privacy', not settings.collect_dob, 'The controlled pilot does not collect dates of birth.')
    return {'ready': all(row['ok'] for row in checks), 'checks': checks,
            'boundary': 'Configuration only. Verify HTTPS, provider policies, email, database access, backups and railway source contracts separately.'}


if __name__ == '__main__':
    result = check()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['ready'] else 1)
