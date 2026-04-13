from httpx import AsyncClient, ASGITransport


async def test_system_status_ok(auth_headers):
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/system/status", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"
    assert data["backend"] == "geo-viz-engine-python"
    assert "timestamp" in data


async def test_system_status_missing_token():
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/system/status")
    assert response.status_code == 401


async def test_system_status_invalid_token():
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/system/status",
            headers={"X-API-Token": "completely-wrong-token"},
        )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing API token"
