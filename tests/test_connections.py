import pytest

from app import connections as cx
from app import settings
from app.auth import explain

GOOD = {"name": "Contoso", "tenant": "contoso.onmicrosoft.com",
        "client_id": "1b2c3d4e-1111-2222-3333-444455556666"}


@pytest.fixture(autouse=True)
def tmp_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "_PATH", tmp_path / "settings.json")


def test_valid_connection():
    assert cx.validate(GOOD) == []
    assert cx.validate({**GOOD, "tenant": "AAAABBBB-1111-2222-3333-444455556666"}) == []


@pytest.mark.parametrize("field,value", [
    ("name", ""), ("tenant", ""), ("tenant", "not a tenant"), ("tenant", "organizations"),
    ("client_id", ""), ("client_id", "abc"), ("client_id", "00000000-0000-0000-0000-000000000000"),
])
def test_invalid_connection(field, value):
    assert cx.validate({**GOOD, field: value})


def test_authority_uses_own_tenant():
    assert cx.authority({**GOOD, "tenant": " Contoso.OnMicrosoft.com "}) == \
        "https://login.microsoftonline.com/contoso.onmicrosoft.com"


def test_save_rename_remove():
    cx.upsert(GOOD)
    cx.upsert({**GOOD, "name": "Fabrikam", "tenant": "fabrikam.com"})
    assert [c["name"] for c in cx.load_all()] == ["Contoso", "Fabrikam"]
    cx.upsert({**GOOD, "name": "Contoso Ltd"}, old_name="Contoso")
    assert [c["name"] for c in cx.load_all()] == ["Contoso Ltd", "Fabrikam"]
    assert cx.last_used() == "Contoso Ltd"
    cx.remove("fabrikam")
    assert [c["name"] for c in cx.load_all()] == ["Contoso Ltd"]


def test_eula_acceptance_kept_when_saving_connections():
    settings.accept_eula()
    cx.upsert(GOOD)
    assert settings.eula_accepted()


def test_friendly_sign_in_errors():
    assert "not found in this tenant" in explain("AADSTS700016: Application with identifier ... was not found")
    assert "Allow public client flows" in explain("AADSTS7000218: The request body must contain client_secret")
    assert explain("something else") == "something else"
