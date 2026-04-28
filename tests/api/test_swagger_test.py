import pytest
from httpx import AsyncClient
from fastapi import FastAPI


@pytest.mark.anyio
async def test_swagger_test_endpoint_returns_valid_openapi(app: FastAPI):
    """
    Test that the /swagger-test endpoint returns a valid OpenAPI spec.
    
    Verifies:
    - Status code 200
    - Response contains "paths" key
    - Known router prefixes (/athletes, /health) are present in the spec
    """
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        response = await client.get("/swagger-test")
        
        assert response.status_code == 200
        data = response.json()
        
        # Assert response contains paths key
        assert "paths" in data
        
        # Assert known router prefixes are present
        paths = data["paths"]
        assert "/athletes/" in paths or "/athletes" in paths
        assert "/health/live" in paths
        assert "/health/ready" in paths
