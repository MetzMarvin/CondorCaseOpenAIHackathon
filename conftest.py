import pytest

@pytest.fixture(autouse=True)
def offline_configuration(monkeypatch):
    monkeypatch.setenv("AI_MODE", "offline")
    monkeypatch.setenv("CONDOR_PREPARATION_MODE", "offline")
