"""Keep local credentials and auth policies out of isolated test applications."""
import pytest


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    for key, value in {'APP_ENV': 'development', 'AUTH_MODE': 'demo', 'DEPLOYMENT_DIVISION': 'demo',
                       'REQUIRE_MFA': 'false', 'PUBLIC_SIGNUP_ENABLED': 'true', 'COLLECT_DATE_OF_BIRTH': 'false',
                       'AI_DATA_POLICY': 'disabled', 'SUPABASE_SERVICE_ROLE_KEY': '',
                       'SEED_DEMO': 'true', 'SOLVE_SECONDS': '3'}.items():
        monkeypatch.setenv(key, value)
