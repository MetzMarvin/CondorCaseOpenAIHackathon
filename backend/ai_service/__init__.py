"""System 2 interface; workflow implementations must satisfy CaseProcessor."""
from typing import Protocol

from backend.contracts import RunRequest, RunResult
from backend.ai_service.workflow import ProgressCallback, process_case

__all__ = ["CaseProcessor", "ProgressCallback", "process_case"]


class CaseProcessor(Protocol):
    def process_case(self, request: RunRequest, emit_progress: ProgressCallback) -> RunResult:
        """Assess a read-only snapshot synchronously; return proposals, never execute them."""
        ...

