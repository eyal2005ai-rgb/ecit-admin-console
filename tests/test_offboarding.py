import json

import pytest

from app import audit
from app.graph import GraphError
from app.tasks import offboarding as ob
from app.tasks.base import Status

USER = {"id": "u1", "displayName": "Dana Levi", "userPrincipalName": "dana@contoso.com",
        "accountEnabled": True, "assignedLicenses": [{}]}
ALL = [s[0] for s in ob.STEPS]

METHODS = [
    {"@odata.type": "#microsoft.graph.passwordAuthenticationMethod", "id": "pw"},
    {"@odata.type": "#microsoft.graph.phoneAuthenticationMethod", "id": ob.MOBILE_PHONE_ID,
     "phoneType": "mobile", "phoneNumber": "+972 501234567"},
    {"@odata.type": "#microsoft.graph.phoneAuthenticationMethod", "id": "b6332ec1-7057-4abe-9331-3d72feddfe41",
     "phoneType": "alternateMobile", "phoneNumber": "+972 529999999"},
    {"@odata.type": "#microsoft.graph.microsoftAuthenticatorAuthenticationMethod", "id": "auth1",
     "displayName": "iPhone 15"},
]


class FakeGraph:
    """Default method (authenticator) can only be deleted after the others are gone."""

    def __init__(self, fail_password=False, default_id="auth1"):
        self.calls = []
        self.methods = [dict(m) for m in METHODS]
        self.fail_password = fail_password
        self.default_id = default_id

    def list_auth_methods(self, uid):
        return list(self.methods)

    def patch(self, path, body):
        self.calls.append(("PATCH", path, body))
        if "passwordProfile" in body and self.fail_password:
            raise GraphError(403, "Authorization_RequestDenied", "Insufficient privileges")

    def post(self, path, body=None):
        self.calls.append(("POST", path, body))

    def delete(self, path):
        mid = path.rsplit("/", 1)[-1]
        others = [m for m in self.methods if m["id"] not in (mid, "pw")]
        if mid == self.default_id and others:
            raise GraphError(400, "badRequest", "Cannot delete default method")
        self.calls.append(("DELETE", path, None))
        self.methods = [m for m in self.methods if m["id"] != mid]


def test_plan_lists_methods_but_changes_nothing():
    g = FakeGraph()
    plan = ob.build_plan(g, USER, ALL)
    assert [p.step_id for p in plan] == ALL
    mfa = next(p for p in plan if p.step_id == ob.STEP_MFA)
    assert len(mfa.actions) == 3                       # password method excluded
    assert any("Authenticator on iPhone 15" in a for a in mfa.actions)
    assert all("501234567" not in a for a in mfa.actions)  # phone numbers masked
    assert g.calls == []                               # dry run made no calls that change data


def test_execute_order_and_default_method_retry():
    g = FakeGraph()
    results = ob.execute(g, USER, ALL)
    assert [r.status for r in results] == [Status.OK] * 4
    kinds = [(c[0], c[1]) for c in g.calls]
    assert kinds[0] == ("PATCH", "/users/u1")                         # block first
    assert g.calls[0][2] == {"accountEnabled": False}
    assert "passwordProfile" in g.calls[1][2]                          # then password
    assert kinds[-1] == ("POST", "/users/u1/revokeSignInSessions")     # revoke last
    deleted = [c[1] for c in g.calls if c[0] == "DELETE"]
    assert deleted.index(f"/users/u1/authentication/phoneMethods/{ob.MOBILE_PHONE_ID}") > \
        deleted.index("/users/u1/authentication/phoneMethods/b6332ec1-7057-4abe-9331-3d72feddfe41")
    assert deleted[-1].endswith("/microsoftAuthenticatorMethods/auth1")
    assert [m["id"] for m in g.methods] == ["pw"]


def test_password_not_leaked_and_failure_does_not_stop_others():
    g = FakeGraph(fail_password=True)
    results = ob.execute(g, USER, ALL)
    by = {r.step_id: r for r in results}
    assert by[ob.STEP_PASSWORD].status == Status.FAILED
    assert "Access denied" in by[ob.STEP_PASSWORD].detail
    assert by[ob.STEP_REVOKE].status == Status.OK
    pw = g.calls[1][2]["passwordProfile"]["password"]
    assert all(pw not in (r.detail + " ".join(r.items)) for r in results)


def test_unselected_steps_skipped():
    g = FakeGraph()
    results = ob.execute(g, USER, [ob.STEP_BLOCK])
    assert [r.status for r in results] == [Status.OK, Status.SKIPPED, Status.SKIPPED, Status.SKIPPED]
    assert len(g.calls) == 1


def test_cannot_offboard_self():
    with pytest.raises(ob.TargetNotAllowed):
        ob.validate_target(USER, "DANA@contoso.com")
    assert ob.validate_target({**USER, "accountEnabled": False}, "admin@contoso.com")


def test_password_generator_strength():
    for _ in range(50):
        pw = ob.generate_password()
        assert len(pw) == 24
        assert any(c.isupper() for c in pw) and any(c.islower() for c in pw)
        assert any(c.isdigit() for c in pw) and any(not c.isalnum() for c in pw)


def test_audit_jsonl_and_pdf(tmp_path):
    g = FakeGraph(fail_password=True)
    results = ob.execute(g, USER, ALL)
    rec = audit.build_record("offboarding", {"id": "t1", "displayName": "Contoso"},
                             "admin@contoso.com", USER, results)
    p = audit.append_jsonl(rec, tmp_path)
    line = json.loads(p.read_text().splitlines()[0])
    assert line["target"]["upn"] == "dana@contoso.com" and line["admin"] == "admin@contoso.com"
    pdf = audit.write_pdf(rec, tmp_path)
    assert pdf.exists() and pdf.read_bytes()[:4] == b"%PDF"
