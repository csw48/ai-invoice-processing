"""Fire-and-forget processing log writer. Errors are silently swallowed so a
logging failure never breaks the invoice pipeline."""

import json
import time
from contextlib import contextmanager
from typing import Any, Callable, Generator
from uuid import UUID


LogFn = Callable[[str, dict, dict | None, int, str | None, UUID | None], None]
LogEntry = tuple[str, dict, dict | None, int, str | None, UUID | None]


class BufferedLogFn:
    """Collect log calls so they can be flushed after invoice persistence."""

    def __init__(self) -> None:
        self.entries: list[LogEntry] = []

    def __call__(
        self,
        agent_name: str,
        input_data: dict,
        output_data: dict | None,
        duration_ms: int,
        error: str | None,
        invoice_id: UUID | None = None,
    ) -> None:
        self.entries.append((agent_name, input_data, output_data, duration_ms, error, invoice_id))

    def flush_to(self, log_fn: LogFn | None) -> None:
        if log_fn is None:
            return
        for entry in self.entries:
            log_fn(*entry)


def make_logger(supabase_client) -> LogFn | None:
    """Return a log function bound to the given Supabase client, or None if no client."""
    if supabase_client is None:
        return None

    def log(
        agent_name: str,
        input_data: dict,
        output_data: dict | None,
        duration_ms: int,
        error: str | None,
        invoice_id: UUID | None = None,
    ) -> None:
        try:
            row: dict[str, Any] = {
                "agent_name": agent_name,
                "input": json.dumps(input_data) if input_data else None,
                "output": json.dumps(output_data) if output_data else None,
                "duration_ms": duration_ms,
                "error": error,
            }
            if invoice_id is not None:
                row["invoice_id"] = str(invoice_id)
            supabase_client.table("processing_logs").insert(row).execute()
        except Exception:
            pass  # never propagate logging errors

    return log


@contextmanager
def timed_step(
    log_fn: LogFn | None,
    agent_name: str,
    input_data: dict,
    invoice_id: UUID | None = None,
) -> Generator[list, None, None]:
    """Context manager that times a pipeline step and calls log_fn on exit.

    Usage:
        with timed_step(log_fn, "extract", {"chars": len(text)}) as out:
            result = do_work()
            out.append({"field_count": ...})  # optional output summary
    """
    start = time.monotonic()
    output_holder: list[dict] = []
    error: str | None = None
    try:
        yield output_holder
    except Exception as exc:
        error = str(exc)
        raise
    finally:
        duration_ms = int((time.monotonic() - start) * 1000)
        if log_fn is not None:
            output_data = output_holder[0] if output_holder else None
            log_fn(agent_name, input_data, output_data, duration_ms, error, invoice_id)
