---
**Feature name (snake_case):** `swagger_test_endpoint`

**Implementation Plan**

1. **Add utility function to generate OpenAPI JSON**
   - **Objective:** Create a reusable helper that returns the FastAPI app’s OpenAPI schema.
   - **Files:**
     - `app/api/utils.py` [CREATE]
   - **Actions:**
     - Import `FastAPI` and `get_openapi` from `fastapi`.
     - Define `def get_openapi_schema(app: FastAPI) -> dict:` that calls `get_openapi(title=app.title, version=app.version, routes=app.routes)`.
     - Include a docstring explaining the purpose (exposes the generated Swagger/OpenAPI spec for testing).

2. **Create a new router for Swagger testing**
   - **Objective:** Expose a simple endpoint that returns the OpenAPI JSON, useful for sanity‑checking all mounted routers.
   - **Files:**
     - `app/api/swagger_test.py` [CREATE]
   - **Actions:**
     - Import `APIRouter`, `Request`, and `JSONResponse` from `fastapi` and the `get_openapi_schema` utility.
     - Instantiate `router = APIRouter()`.
     - Add route `@router.get("/swagger-test", summary="Return OpenAPI spec for testing")` that receives the global FastAPI app via `request.app` and returns `get_openapi_schema(request.app)`.
     - Return the schema with `return JSONResponse(content=schema)`.

3. **Register the Swagger test router with the main FastAPI app**
   - **Objective:** Make the new endpoint available under the API root.
   - **Files:**
     - `app/main.py` [MODIFY]
   - **Actions:**
     - Import `router as swagger_test_router` from `app.api.swagger_test`.
     - Include the router with `app.include_router(swagger_test_router, tags=["Swagger Test"])`.

4. **Verify OpenAPI configuration consistency**
   - **Objective:** Ensure the generated schema is consistent with the existing `/docs` and `/openapi.json` endpoints.
   - **Files:**
     - `app/main.py` [MODIFY]
   - **Actions:**
     - Confirm `FastAPI(..., openapi_url="/openapi.json", docs_url="/docs")` is set (no change needed if already present).
     - If a custom `openapi_url` exists, ensure it aligns with the schema returned by the test endpoint.

5. **Add a minimal test for the new endpoint**
   - **Objective:** Confirm the endpoint returns a valid OpenAPI spec and includes all routers.
   - **Files:**
     - `tests/api/test_swagger_test.py` [CREATE]
   - **Actions:**
     - Use `AsyncClient` from `httpx` with the FastAPI `app`.
     - Perform `GET /swagger-test` and assert status `200`.
     - Assert the response JSON contains a `"paths"` key and that known router prefixes (e.g., `/athlete`, `/health`) are present.
---
