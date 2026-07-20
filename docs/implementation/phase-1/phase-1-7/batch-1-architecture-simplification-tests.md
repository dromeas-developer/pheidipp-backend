> **Baseline — test companion for** `batch-1-architecture-simplification.md`, migrated from `docs/implementation/phase-1/phase-1-7-p1-architecture-simplification.md` and `phase-1-8-p1-fix-event-ordering-and-async-processing.md` **on** 2026-07-19.

## Test Scenarios

Derived from the test manifests (`tests/test-manifest/phase-1-7.yaml`, `tests/test-manifest/phase-1-8.yaml`) and actual test files.

### Infrastructure

**Task execution:**
- Given `fit_ingest` task enqueued via procrastinate, worker picks it up and completes successfully
- Given `recalibrate_twin` task enqueued, worker completes
- Given procratinate worker process (`procrastinate --app=app.worker.app worker`) starts without errors
- Given Redis is absent from docker-compose, all services start without Redis dependency

**Object storage:**
- Given MinIO service running, `ObjectStorageClient.upload_fit()` succeeds against MinIO endpoint
- Given `ObjectStorageClient.download_fit()` retrieves previously uploaded FIT bytes
- Given `ObjectStorageClient.exists()` confirms key presence after upload
- Given no S3_ENDPOINT_URL configured, client falls back to local filesystem at `./var/object-storage`

### Pipeline Wiring

**POST /upload endpoint:**
- Given uploading a valid FIT file, returns 202 Accepted with task_id immediately
- Given Activity record created with source=manual_upload, fit_file_key set, load scores null
- Given `fit_ingest` task enqueued with correct activity_id and athlete_id
- Given object storage failure during upload, returns 503 and creates no Activity record
- Given `GET /athletes/{id}/activities/{aid}`, shows null load scores immediately after upload (before worker runs)

**Worker task execution:**
- Given `fit_ingest` task executes, downloads FIT from object storage, parses it, computes load scores
- Given after task completes, Activity has populated aerobic_load and non-null fit_file_key
- Given `GET /athletes/{id}/twin/history` shows new TwinState after task completion
- Given task failures (FIT parse error, load computation error), Activity remains with null loads for retry

**Event ordering:**
- Given `activity_ingested` event fired within the worker transaction (transactional outbox pattern)
- Given events published in order: `sport_type_detected` → `activity_ingested` → `activity_calibration_eligible`
- Given event not published before the producing transaction commits
- Given `signal_clean` task deferred within `_run_ingestion_pipeline()` before commit

**Backward compatibility:**
- Given `POST /analyse` continues to work
- Given `GET /activities` returns activities with correct fields
- Given `GET /athletes/{id}/twin` returns current TwinState
- Given all existing test fixtures that use sync `ingest()` continue to pass
