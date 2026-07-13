"""
AccessAI — Test Suite
pytest + httpx AsyncClient
"""
import pytest
import json
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport

# We'll import the app lazily to avoid DB init at test collection time
@pytest.fixture
async def client():
    from main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_scan_invalid_url(client):
    r = await client.post("/api/scan/start", json={"url": "not-a-url"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_scan_missing_url(client):
    r = await client.post("/api/scan/start", json={})
    assert r.status_code == 422  # pydantic validation


@pytest.mark.asyncio
async def test_scan_start_valid_url(client):
    with patch("backend.services.scan_service.ScanService.create_scan", new_callable=AsyncMock) as mock_create, \
         patch("backend.services.scan_service.ScanService.run_scan_background", new_callable=AsyncMock):
        mock_create.return_value = "abc12345"
        r = await client.post("/api/scan/start", json={"url": "https://example.com", "model": "llama3"})
        assert r.status_code == 200
        assert "scan_id" in r.json()


@pytest.mark.asyncio
async def test_scan_status_not_found(client):
    r = await client.get("/api/scan/nonexistent/status")
    assert r.status_code == 404


# ---- Unit tests for scanner logic ----
def test_severity_mapping():
    from backend.scanner.axe_scanner import AccessibilityScanner
    s = AccessibilityScanner()
    v = {"id": "test", "impact": "critical", "tags": ["wcag111"], "nodes": []}
    result = s._classify(v)
    assert result["severity"] == "critical"


def test_score_calculation():
    from backend.scanner.axe_scanner import AccessibilityScanner
    s = AccessibilityScanner()
    violations = [
        {"severity": "critical"},
        {"severity": "high"},
        {"severity": "low"},
    ]
    score = s._calculate_score(violations, passed_count=50)
    assert 0 <= score <= 100


def test_url_validation():
    from backend.utils.validators import validate_url
    assert validate_url("https://example.com") == (True, "")
    assert validate_url("javascript:alert(1)")[0] is False
    assert validate_url("")[0] is False
    assert validate_url("ftp://example.com")[0] is False


def test_json_parse_robustness():
    from backend.ai_engine.ollama_service import OllamaClient
    client = OllamaClient()

    # Clean JSON
    assert client.parse_json('{"key":"val"}') == {"key": "val"}

    # Markdown fenced
    assert client.parse_json('```json\n{"key":"val"}\n```') == {"key": "val"}

    # Embedded in text
    result = client.parse_json('Here is the result:\n{"key":"val"}\nDone.')
    assert result == {"key": "val"}

    # Garbage
    assert client.parse_json("No JSON here") is None
