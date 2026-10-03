# -*- coding: utf-8 -*-
"""
Tests for Web API Reference & Documentation Endpoints.
Xác thực /docs/api/openapi.json, /docs/api/swagger, /docs/api/redoc, các redirect tương thích ngược và bộ tệp docs/api/*.
"""

from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check_endpoint():
    """Kiểm tra endpoint /health trả về status 200 và thông tin app."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "AI Prompt Studio" in data["app"]


def test_openapi_schema_endpoint():
    """Kiểm tra /docs/api/openapi.json trả về metadata OpenAPI v3 đầy đủ."""
    response = client.get("/docs/api/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["openapi"].startswith("3.")
    assert schema["info"]["title"] == "AI Prompt Studio API"
    assert schema["info"]["version"] == "1.1.0"
    assert "tags" in schema
    tag_names = [t["name"] for t in schema["tags"]]
    assert "prompts" in tag_names
    assert "ai" in tag_names
    assert "/api/stats" in schema["paths"]
    summary = schema["paths"]["/api/stats"]["get"]["summary"]
    assert "thống kê" in summary.lower() or "stats" in summary.lower()


def test_swagger_ui_endpoint():
    """Kiểm tra Swagger UI tại /docs/api/swagger trả về HTML 200."""
    response = client.get("/docs/api/swagger")
    assert response.status_code == 200
    assert "swagger-ui" in response.text.lower() or "html" in response.text.lower()


def test_redoc_endpoint():
    """Kiểm tra ReDoc tại /docs/api/redoc trả về HTML 200."""
    response = client.get("/docs/api/redoc")
    assert response.status_code == 200
    assert "redoc" in response.text.lower()


def test_docs_api_hub_and_redirects():
    """Kiểm tra các redirect từ URL cũ và /docs/api hub."""
    # /docs/api -> /docs/api/swagger
    resp = client.get("/docs/api", follow_redirects=False)
    assert resp.status_code in [307, 302]
    assert resp.headers["location"] == "/docs/api/swagger"

    # /docs -> /docs/api/swagger
    resp = client.get("/docs", follow_redirects=False)
    assert resp.status_code in [307, 302]
    assert resp.headers["location"] == "/docs/api/swagger"

    # /redoc -> /docs/api/redoc
    resp = client.get("/redoc", follow_redirects=False)
    assert resp.status_code in [307, 302]
    assert resp.headers["location"] == "/docs/api/redoc"

    # /openapi.json -> /docs/api/openapi.json
    resp = client.get("/openapi.json", follow_redirects=False)
    assert resp.status_code in [307, 302]
    assert resp.headers["location"] == "/docs/api/openapi.json"

    # Following redirects returns 200 OK
    resp_followed = client.get("/openapi.json", follow_redirects=True)
    assert resp_followed.status_code == 200
    assert resp_followed.json()["openapi"].startswith("3.")


def test_static_docs_api_files_exist():
    """Kiểm tra sự tồn tại của bộ tệp tĩnh trong docs/api/."""
    docs_api_dir = Path(__file__).resolve().parent.parent / "docs" / "api"
    assert (docs_api_dir / "openapi.json").exists()
    assert (docs_api_dir / "swagger.html").exists()
    assert (docs_api_dir / "redoc.html").exists()
    assert (docs_api_dir / "index.html").exists()


def test_prompts_list_api_response_schema():
    """Kiểm tra endpoint /api/prompts tuân thủ schema PromptListResponse."""
    response = client.get("/api/prompts?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert "count" in data
    assert "items" in data
    assert "category" in data
    assert len(data["items"]) <= 5


def test_stats_api_response_schema():
    """Kiểm tra endpoint /api/stats tuân thủ schema StatsResponse."""
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_prompts" in data
    assert "total_images" in data
    assert "by_category" in data
