from httpx import AsyncClient, ASGITransport
from app.main import app


async def test_generate_data_default_count(auth_headers):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/data/generate", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["generated_count"] == 10
    assert len(data["wells"]) == 10
    assert "Generated" in data["message"]


async def test_generate_data_custom_count(auth_headers):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/data/generate",
            json={"count": 3},
            headers=auth_headers,
        )
    assert response.status_code == 200
    assert response.json()["generated_count"] == 3
    assert len(response.json()["wells"]) == 3


async def test_generate_data_well_metadata_fields(auth_headers):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/data/generate",
            json={"count": 1},
            headers=auth_headers,
        )
    assert response.status_code == 200
    well = response.json()["wells"][0]
    assert well["well_id"] == "WELL-001"
    assert well["well_name"] == "Well 1"
    assert well["depth_start"] == 0.0
    assert well["depth_end"] > 0.0
    assert set(well["curve_names"]) == {"GR", "RT", "DEN", "NPHI"}


async def test_generate_data_no_body_uses_defaults(auth_headers):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/data/generate", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["generated_count"] == 10


async def test_generate_data_count_zero_rejected(auth_headers):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/data/generate",
            json={"count": 0},
            headers=auth_headers,
        )
    assert response.status_code == 422


async def test_generate_data_count_over_limit_rejected(auth_headers):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/data/generate",
            json={"count": 101},
            headers=auth_headers,
        )
    assert response.status_code == 422


async def test_generate_data_unauthorized():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/data/generate")
    assert response.status_code == 401
