import os

# Must be set before any app module is imported
TEST_TOKEN = "test-token-xxx-32-characters-long"
os.environ.setdefault("GEOVIZ_API_TOKEN", TEST_TOKEN)

import pytest


@pytest.fixture(scope="session")
def test_token() -> str:
    return TEST_TOKEN


@pytest.fixture(scope="session")
def auth_headers() -> dict:
    return {"X-API-Token": TEST_TOKEN}
