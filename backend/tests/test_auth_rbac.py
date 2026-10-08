"""Authentication and authorisation tests."""

from tests.conftest import auth_header, register


def test_register_first_user_becomes_super_admin(client):
    body = register(client, "first@test.local")
    assert body["user"]["role"] == "SUPER_ADMIN"
    assert body["access_token"]


def test_register_second_user_is_plain_user(client):
    register(client, "one@test.local")
    body = register(client, "two@test.local")
    assert body["user"]["role"] == "USER"


def test_duplicate_email_rejected(client):
    register(client, "dupe@test.local")
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "dupe@test.local", "password": "Str0ngPass!2025"},
    )
    assert response.status_code == 400


def test_short_password_rejected(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "short@test.local", "password": "abc"},
    )
    assert response.status_code == 422


def test_login_and_me(client):
    register(client, "login@test.local")
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "login@test.local", "password": "Str0ngPass!2025"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]

    me = client.get("/api/v1/auth/me", headers=auth_header(token))
    assert me.status_code == 200
    assert me.json()["email"] == "login@test.local"


def test_login_rejects_wrong_password(client):
    register(client, "wrong@test.local")
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "wrong@test.local", "password": "nope"},
    )
    assert response.status_code == 401


def test_protected_endpoints_require_token(client):
    for path in ("/api/v1/auth/me", "/api/v1/documents/", "/api/v1/conversations"):
        assert client.get(path).status_code == 401


def test_refresh_token_works(client):
    body = register(client, "refresh@test.local")
    response = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]}
    )
    assert response.status_code == 200
    assert response.json()["access_token"]


def test_invalid_token_rejected(client):
    assert client.get("/api/v1/auth/me", headers=auth_header("not-a-jwt")).status_code == 401


def test_password_is_hashed_not_plaintext(db, client):
    register(client, "hash@test.local")
    from app.models.user import User

    user = db.query(User).filter_by(email="hash@test.local").one()
    assert "Str0ngPass!2025" not in user.hashed_password
    assert user.hashed_password.startswith("$2")


# --------------------------------------------------------------- authorisation
def test_normal_user_cannot_upload_document(client, normal_user):
    response = client.post(
        "/api/v1/documents/upload",
        headers=normal_user["headers"],
        files={"file": ("x.txt", b"hello", "text/plain")},
        data={"title": "Nope"},
    )
    assert response.status_code == 403


def test_normal_user_cannot_list_users(client, normal_user):
    assert client.get("/api/v1/admin/users", headers=normal_user["headers"]).status_code == 403


def test_normal_user_cannot_view_admin_dashboard(client, normal_user):
    assert (
        client.get("/api/v1/admin/dashboard", headers=normal_user["headers"]).status_code == 403
    )


def test_admin_can_view_admin_dashboard(client, admin):
    response = client.get("/api/v1/admin/dashboard", headers=admin["headers"])
    assert response.status_code == 200
    assert "totals" in response.json()


def test_user_cannot_read_another_users_conversation(client, normal_user, db):
    from app.models.chat import Conversation

    other = Conversation(user_id=999, title="Private", mode="SOP_MODE")
    db.add(other)
    db.commit()

    response = client.get(
        f"/api/v1/conversations/{other.id}", headers=normal_user["headers"]
    )
    assert response.status_code == 404


def test_super_admin_cannot_demote_self(client, admin):
    response = client.patch(
        f"/api/v1/admin/users/{admin['id']}",
        headers=admin["headers"],
        json={"role": "USER"},
    )
    assert response.status_code == 400
