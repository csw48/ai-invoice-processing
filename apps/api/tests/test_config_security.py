import pytest

from app.core.config import Settings


def test_production_refuses_to_start_without_auth():
    with pytest.raises(Exception, match="ENABLE_AUTH"):
        Settings(app_env="production", enable_auth=False, _env_file=None)


def test_production_starts_with_auth_enabled():
    settings = Settings(app_env="production", enable_auth=True, _env_file=None)
    assert settings.enable_auth is True


def test_local_dev_runs_without_auth():
    settings = Settings(app_env="local", enable_auth=False, _env_file=None)
    assert settings.enable_auth is False
