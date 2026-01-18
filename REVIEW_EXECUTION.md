Code Review Feedback

Findings

1) High: Manual trigger creates a WinternRun but uses get_async_session (no auto-commit), so the run is never persisted and the returned run_id can point to a row that never exists. This breaks GET /runs/{run_id} and any later status checks.
   File: apps/api/src/wintern/execution/router.py:111

2) High: The manual trigger returns a run ID created in the request, but the background task calls execute_wintern, which creates its own run record. The returned run_id is never updated to RUNNING/COMPLETED and you get duplicate runs for a single trigger.
   Files: apps/api/src/wintern/execution/router.py:111, apps/api/src/wintern/execution/executor.py:187

3) Medium: On failure paths, next_run_at is not updated, so scheduled winterns that fail due to missing sources/delivery will remain due and be retried every scheduler interval, creating repeated failure runs. If that is unintended, advance next_run_at on failure too.
   File: apps/api/src/wintern/execution/executor.py:407

Open Questions

- Should manual triggers create the run record in the API layer or inside execute_wintern only? This drives whether the response should be “queued” with a real run ID vs. a lightweight job ID.
- Do you want scheduled failures to advance next_run_at (backoff to next cron tick) or to retry every 5 minutes until configs are fixed?
