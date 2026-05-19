# Add idempotency recheck inside onboarding UoW transaction

## Root Cause

The `onboard_athlete` endpoint performs pre-flight validation (athlete exists, not onboarded, valid status) **outside** the UoW transaction. Between pre-flight and transaction entry, a concurrent request can complete onboarding for the same athlete. Both requests then enter their respective transactions — the second one creates duplicate preferences or conflicts at the training-block level rather than failing cleanly with 409.

## Fix

Add an idempotency recheck **inside** the UoW transaction, before any writes. Re-read the athlete row under the transaction's snapshot and verify `onboarding_complete` is still `False`. If a concurrent request already set it, raise 409 immediately.

---

### API

1. Add idempotency recheck inside onboarding UoW block
   - Objective: Prevent concurrent onboarding requests from both passing pre-flight validation by re-verifying `onboarding_complete` under the transaction
   - File: `app/api/routes/athletes.py` [MODIFY]
   - Actions:
     - Inside the `onboard_athlete` function, within the `async with UnitOfWork(db) as uow:` block, insert the following logic **before** the call to `onboarding_service.complete_onboarding(...)`:
       - Call `athlete = await uow.athletes.get_by_id(athlete_id)` to re-fetch the athlete under the transaction
       - If `athlete` is `None`, raise `HTTPException` with status 404 and detail `"Athlete not found"`
       - If `athlete.onboarding_complete` is `True`, raise `HTTPException` with status 409 and detail `"Onboarding already complete. Use PATCH /athlete-preferences/{id} to update preferences, or close the current training block before starting a new one."`
     - Remove the now-stale comment block that reads `"Pre-flight validation already confirmed athlete exists and is not onboarded. The service's internal operations handle idempotency..."`
