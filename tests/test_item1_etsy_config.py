"""Item 1 — Etsy config names unified with deprecation alias + boolean-only status."""
import os
import pytest


@pytest.fixture(autouse=True)
def _reset_state():
    """Reset the module-level deprecation registry so each test sees fresh state."""
    from agents.capabilities import marketplace as m
    if hasattr(m, "_deprecation_once_logged"):
        m._deprecation_once_logged.clear()
    yield
    if hasattr(m, "_deprecation_once_logged"):
        m._deprecation_once_logged.clear()


def _set_canonical():
    os.environ["ETSY_KEYSTRING"] = "KEY"
    os.environ["ETSY_SHARED_SECRET"] = "SECRET"
    os.environ["ETSY_REFRESH_TOKEN"] = "REFRESH"
    os.environ["ETSY_SHOP_ID"] = "12345"
    os.environ["ETSY_TAXONOMY_ID"] = "116"


def _clear():
    for k in ("ETSY_KEYSTRING", "ETSY_SHARED_SECRET", "ETSY_REFRESH_TOKEN",
              "ETSY_SHOP_ID", "ETSY_TAXONOMY_ID", "ETSY_API_KEY", "ETSY_ACCESS_TOKEN"):
        os.environ.pop(k, None)


def test_etsy_config_status_all_set():
    _clear(); _set_canonical()
    from agents.capabilities import marketplace as m
    status = m.etsy_config_status()
    assert status["etsy_configured"] is True
    assert all(v is True for k, v in status.items() if k != "etsy_configured")


def test_etsy_config_status_missing_each():
    _clear()
    from agents.capabilities import marketplace as m
    assert m.etsy_config_status()["etsy_configured"] is False
    _set_canonical()
    os.environ.pop("ETSY_KEYSTRING")
    assert m.etsy_config_status()["etsy_keystring"] is False
    assert m.etsy_config_status()["etsy_configured"] is False


def test_deprecated_alias_maps_to_canonical(monkeypatch, capsys):
    _clear()
    os.environ["ETSY_API_KEY"] = "LEGACY_KEY"
    os.environ["ETSY_SHARED_SECRET"] = "SS"
    os.environ["ETSY_REFRESH_TOKEN"] = "REFRESH"
    os.environ["ETSY_SHOP_ID"] = "123"
    from agents.capabilities import marketplace as m
    cfg = m._read_env()
    assert cfg["keystring"] == "LEGACY_KEY"
    assert m.etsy_config_status()["etsy_configured"] is True
    captured = capsys.readouterr()
    assert "ETSY_API_KEY" in captured.out


def test_deprecated_alias_does_not_warn_twice(monkeypatch, capsys):
    _clear()
    os.environ["ETSY_API_KEY"] = "LEGACY_KEY"
    os.environ["ETSY_SHARED_SECRET"] = "SS"
    os.environ["ETSY_REFRESH_TOKEN"] = "REFRESH"
    os.environ["ETSY_SHOP_ID"] = "123"
    from agents.capabilities import marketplace as m
    m._read_env()
    m._read_env()
    captured = capsys.readouterr()
    assert captured.out.count("WARNING") == 1