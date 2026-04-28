from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.api.utils import get_openapi_schema

router = APIRouter()


@router.get("/swagger-test", summary="Return OpenAPI spec for testing")
async def swagger_test_endpoint(request: Request):
    """
    Return the FastAPI application's OpenAPI schema as JSON.
    
    This endpoint is useful for sanity-checking all mounted routers and
    verifying that the OpenAPI documentation is correctly generated.
    """
    schema = get_openapi_schema(request.app)
    return JSONResponse(content=schema)
