"""Execution module - executor, scheduler, and run management."""

from wintern.execution.executor import (
    ExecutionError,
    NoContentFoundError,
    NoDeliveryConfiguredError,
    NoSourcesConfiguredError,
    execute_wintern,
)
from wintern.execution.factories import (
    UnsupportedDeliveryError,
    UnsupportedSourceError,
    create_data_source,
    create_delivery_channel,
)
from wintern.execution.models import RunStatus, SeenContent, WinternRun
from wintern.execution.router import router as execution_router
from wintern.execution.scheduler import (
    check_and_run_due_winterns,
    get_scheduler,
    setup_scheduler,
    shutdown_scheduler,
    start_scheduler,
)
from wintern.execution.schemas import (
    TriggerRunResponse,
    WinternRunListResponse,
    WinternRunResponse,
)
from wintern.execution.service import (
    calculate_next_run_at,
    complete_run,
    compute_content_hash,
    create_run,
    fail_run,
    get_due_winterns,
    get_run_by_id,
    get_seen_hashes,
    get_wintern_for_execution,
    list_runs_for_wintern,
    record_seen_content,
    record_seen_content_batch,
    start_run,
    update_next_run_at,
)

__all__ = [
    # Executor
    "ExecutionError",
    "NoContentFoundError",
    "NoDeliveryConfiguredError",
    "NoSourcesConfiguredError",
    # Models
    "RunStatus",
    "SeenContent",
    # Schemas
    "TriggerRunResponse",
    # Factories
    "UnsupportedDeliveryError",
    "UnsupportedSourceError",
    "WinternRun",
    "WinternRunListResponse",
    "WinternRunResponse",
    # Service
    "calculate_next_run_at",
    # Scheduler
    "check_and_run_due_winterns",
    "complete_run",
    "compute_content_hash",
    "create_data_source",
    "create_delivery_channel",
    "create_run",
    "execute_wintern",
    # Router
    "execution_router",
    "fail_run",
    "get_due_winterns",
    "get_run_by_id",
    "get_scheduler",
    "get_seen_hashes",
    "get_wintern_for_execution",
    "list_runs_for_wintern",
    "record_seen_content",
    "record_seen_content_batch",
    "setup_scheduler",
    "shutdown_scheduler",
    "start_run",
    "start_scheduler",
    "update_next_run_at",
]
