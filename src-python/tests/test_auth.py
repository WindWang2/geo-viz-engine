import os
import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from app.auth import AuthTokenMiddleware


def make_test_app(token: str) -> FastAPI:
    """Create a minimal FastAPI app with auth middleware for testing."""
    app = FastAPI()
    app.add_middleware(AuthTokenMiddleware)

    @app.get("/ping")
    async def ping():
        return JSONResponse({"pong": True})

    return app


async def test_valid_token_passes(test_token):
    app = make_test_app(test_token)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/ping", headers={"X-API-Token": test_token})
    assert response.status_code == 200
    assert response.json() == {"pong": True}


async def test_missing_token_returns_401(test_token):
    app = make_test_app(test_token)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/ping")
    assert response.status_code == 401
    assert "detail" in response.json()


async def test_wrong_token_returns_401(test_token):
    app = make_test_app(test_token)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/ping", headers={"X-API-Token": "not-the-right-token"})
    assert response.status_code == 401


async def test_empty_token_returns_401(test_token):
    app = make_test_app(test_token)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/ping", headers={"X-API-Token": ""})
    assert response.status_code == 401
