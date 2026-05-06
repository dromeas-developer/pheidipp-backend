---
id: ADR-001
status: accepted
tags: [architecture, layer]
supersedes: ~
superseded-by: ~
---

# ADR 001: Layer Architecture

## Rules
**LayerOrder**: Enforce the following layer dependency order: `api → services → repositories → models`.
**NoLayerSkip**: No layer may skip its immediate downstream layer (e.g., `api` may not call `repositories` directly).
**BusinessLogic**: All business logic must reside in the `services` layer.
**RepositoryAccess**: Repository access is exclusively permitted from the `services` layer.
**AgentIntegration**: Agents must interact with the system exclusively through the `services` layer.
**WorkerIntegration**: Background jobs must interact with the system exclusively through the `services` layer.

## Decision
The layer architecture `api → services → repositories → models` was adopted to enforce strict separation of concerns and maintainability. This structure ensures that business logic is centralized in the `services` layer, preventing scattered logic and enabling consistent testability and reusability.

## Rationale
- **Centralized Business Logic**: Ensures all business rules are implemented in one place, reducing duplication and inconsistency.
- **Testability**: Isolating business logic in the `services` layer simplifies unit testing without requiring HTTP or database dependencies.
- **Maintainability**: Clear layer boundaries reduce cognitive load and make the system easier to refactor or extend.
- **Security**: Restricting repository access to the `services` layer minimizes the risk of direct data manipulation from external layers.
- **Reusability**: The `services` layer can be reused by multiple entry points (API, agents, workers) without modification.
- **Consistency**: Enforces a uniform pattern for data flow, reducing ad-hoc implementations.

## Alternatives Rejected

| Option | Why Rejected |
|---|---|
| Flat Architecture | Leads to scattered business logic, poor testability, and reduced maintainability. |
| Direct Repository Access from API | Violates separation of concerns and increases security risks. |
| Layer Skipping (e.g., API → Repositories) | Undermines the `services` layer, leading to inconsistent business logic enforcement. |
| Microservices per Layer | Overly complex for the current scale and introduces unnecessary operational overhead. |

## Tradeoffs
- **Pro**: Strict separation of concerns improves maintainability and testability.
- **Pro**: Centralized business logic reduces duplication and enforces consistency.
- **Con**: Additional boilerplate for simple CRUD operations.
- **Con**: Slightly increased latency due to layer traversal (negligible in practice).

## Compliance

**Compliant**
```python
# API layer calling the services layer
@router.post("/athletes")
async def create_athlete(athlete_data: AthleteCreate, service: AthleteService = Depends()):
    return await service.create_athlete(athlete_data)
```

**Non-compliant**
```python
# API layer skipping the services layer and calling repositories directly
@router.post("/athletes")
async def create_athlete(athlete_data: AthleteCreate, repo: AthleteRepository = Depends()):
    return await repo.create(athlete_data)
```

## Cross-References
None.