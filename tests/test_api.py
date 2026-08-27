import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.services.sanitizer import PrivacySanitizer

client = TestClient(app)
AUTH_HEADERS = {"x-api-key": settings.API_SECRET_KEY}


def test_privacy_sanitizer():
    """Verify that paths are sanitized and sensitive files are blocked."""
    assert PrivacySanitizer.is_sensitive(".env") is True
    assert PrivacySanitizer.is_sensitive("config/.env.local") is True
    assert PrivacySanitizer.is_sensitive("id_rsa") is True
    assert PrivacySanitizer.is_sensitive("secrets.key") is True
    assert PrivacySanitizer.is_sensitive("credentials.json") is True

    assert PrivacySanitizer.is_ignored_directory("node_modules/react/index.js") is True
    assert PrivacySanitizer.is_ignored_directory(".git/config") is True

    raw = r"D:\SOURCE CODE\velocity\app\main.py"
    sanitized, lang, ext = PrivacySanitizer.sanitize_path(raw, "velocity")
    assert sanitized == "velocity/app/main.py"
    assert lang == "python"
    assert ext == ".py"


def test_auth_rejection():
    """Endpoints requiring authentication should reject requests without a valid key."""
    res = client.get("/api/v1/stats/today")
    assert res.status_code == 401

    res = client.post("/api/v1/ingest/heartbeat", json={"project_name": "test"})
    assert res.status_code == 401


def test_developer_api_key_lifecycle():
    """Test generating a developer key (OpenAI style), using it, tracking requests, and revoking it."""
    # 1. Create key
    res = client.post("/api/v1/keys", json={"name": "Lifecycle App"}, headers=AUTH_HEADERS)
    assert res.status_code == 200
    key_data = res.json()
    dev_key = key_data["key"]
    key_id = key_data["id"]

    # 2. Query with dev key
    dev_headers = {"x-api-key": dev_key}
    stats_res = client.get("/api/v1/stats/today", headers=dev_headers)
    assert stats_res.status_code == 200

    # 3. Verify total_requests incremented
    list_res = client.get("/api/v1/keys", headers=AUTH_HEADERS)
    assert list_res.status_code == 200
    keys = list_res.json()
    created_record = next(k for k in keys if k["id"] == key_id)
    assert created_record["total_requests"] >= 1

    # 4. Revoke key
    del_res = client.delete(f"/api/v1/keys/{key_id}", headers=AUTH_HEADERS)
    assert del_res.status_code == 200

    # 5. Revoked key gives 401
    revoked_res = client.get("/api/v1/stats/today", headers=dev_headers)
    assert revoked_res.status_code == 401


def test_multi_tenant_user_isolation():
    """Verify that User A (Rohit) and User B (Priya) have 100% isolated telemetry data."""
    # 1. Create Key for User A (Rohit)
    res_a = client.post("/api/v1/keys", json={"name": "Rohit's PC"}, headers=AUTH_HEADERS)
    assert res_a.status_code == 200
    key_a = res_a.json()["key"]
    headers_a = {"x-api-key": key_a}

    # 2. Create Key for User B (Priya)
    res_b = client.post("/api/v1/keys", json={"name": "Priya's MacBook"}, headers=AUTH_HEADERS)
    assert res_b.status_code == 200
    key_b = res_b.json()["key"]
    headers_b = {"x-api-key": key_b}

    # 3. User A logs activity for project "Project-Alpha"
    client.post(
        "/api/v1/ingest/heartbeat",
        json={"project_name": "Project-Alpha", "language": "python", "file_extension": ".py"},
        headers=headers_a
    )
    client.post(
        "/api/v1/ingest/git-commit",
        json={"project_name": "Project-Alpha", "commit_hash": "aaa111", "commit_message": "Alpha commit"},
        headers=headers_a
    )

    # 4. User B logs activity for project "Project-Beta"
    client.post(
        "/api/v1/ingest/heartbeat",
        json={"project_name": "Project-Beta", "language": "typescript", "file_extension": ".tsx"},
        headers=headers_b
    )
    client.post(
        "/api/v1/ingest/git-commit",
        json={"project_name": "Project-Beta", "commit_hash": "bbb222", "commit_message": "Beta commit"},
        headers=headers_b
    )

    # 5. Query stats as User A -> only sees Alpha
    stats_a = client.get("/api/v1/stats/today", headers=headers_a).json()
    assert "Project-Alpha" in stats_a["active_projects"]
    assert "Project-Beta" not in stats_a["active_projects"]
    assert stats_a["commits_today"] == 1

    # 6. Query stats as User B -> only sees Beta
    stats_b = client.get("/api/v1/stats/today", headers=headers_b).json()
    assert "Project-Beta" in stats_b["active_projects"]
    assert "Project-Alpha" not in stats_b["active_projects"]
    assert stats_b["commits_today"] == 1

    # 7. Query projects list as User A & User B
    projs_a = [p["project_name"] for p in client.get("/api/v1/projects", headers=headers_a).json()]
    projs_b = [p["project_name"] for p in client.get("/api/v1/projects", headers=headers_b).json()]
    assert "Project-Alpha" in projs_a and "Project-Beta" not in projs_a
    assert "Project-Beta" in projs_b and "Project-Alpha" not in projs_b


def test_sensitive_file_ingest_blocked():
    """Ingesting a sensitive file like .env should be safely ignored."""
    payload = {
        "project_name": "velocity",
        "raw_path": r"D:\SOURCE CODE\velocity\.env",
        "event_type": "file_modified"
    }
    res = client.post("/api/v1/ingest/file-event", json=payload, headers=AUTH_HEADERS)
    assert res.status_code == 200
    assert res.json()["status"] == "ignored"


def test_public_zero_leak_status():
    """Verify public endpoint works without auth and leaks zero private data."""
    res = client.get("/api/v1/public/status")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "current_activity_category" in data
    assert "active_hours_today" in data
    assert "project_name" not in data
    assert "sanitized_path" not in data
    assert "commit_message" not in data


def test_ai_standup_generation():
    """Verify AI Standup endpoint generates structured standup report."""
    res = client.get("/api/v1/analytics/standup", headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert "formatted_markdown" in data
    assert "Daily Engineering Standup" in data["formatted_markdown"]
    assert "active_time" in data


def test_one_click_installer_endpoints():
    """Verify installer endpoints deliver valid setup scripts."""
    # Test client.py download
    client_res = client.get("/client.py")
    assert client_res.status_code == 200
    assert "Velocity Standalone" in client_res.text

    # Test PowerShell 1-liner
    ps1_res = client.get("/install.ps1?key=vel_sk_test123")
    assert ps1_res.status_code == 200
    assert "vel_sk_test123" in ps1_res.text
    assert "pythonw.exe" in ps1_res.text

    # Test Bash 1-liner
    sh_res = client.get("/install.sh?key=vel_sk_test123")
    assert sh_res.status_code == 200
    assert "vel_sk_test123" in sh_res.text


if __name__ == "__main__":
    import pytest
    pytest.main(["-v", __file__])
