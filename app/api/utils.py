from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


def get_openapi_schema(app: FastAPI) -> dict:
    """
    Generate and return the OpenAPI schema for a FastAPI application.
    
    This utility function exposes the automatically generated Swagger/OpenAPI
    specification, making it available for testing and validation purposes.
    """
    return get_openapi(
        title=app.title,
        version=app.version,
        routes=app.routes,
    )
