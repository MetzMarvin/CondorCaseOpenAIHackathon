"""Configured System 2 entry point with opt-in, labelled demo fallback."""
import logging
import os
from backend.contracts import ProgressUpdate, RunRequest, RunResult, TechnicalError
from backend.ai_service.settings import Settings
from backend.ai_service.workflow import ProgressCallback, process_case as process_offline


def process_case(request: RunRequest, emit_progress: ProgressCallback) -> RunResult:
    live = False
    callback_failed = False

    def emit(update):
        nonlocal callback_failed
        try:
            emit_progress(update)
        except Exception:
            callback_failed = True
            raise

    try:
        settings = Settings.from_env()
        live = settings.mode == 'openai'
        if not live:
            return process_offline(request, emit)
        # Code owns the supported policy, identity and financial constraints.
        baseline = process_offline(request, lambda _: None)
        if baseline.status == 'FAILED':
            return baseline.model_copy(update={'simulation': False})
        from backend.ai_service.experts import run_experts
        return run_experts(request, baseline, emit, settings)
    except Exception:
        # Only the integrated launcher opts into this behavior. Callback/storage
        # failures must still fail rather than retrying business processing.
        if os.environ.get('AI_FALLBACK_OFFLINE') == '1' and not callback_failed:
            logging.getLogger(__name__).warning(
                'Live AI unavailable or invalid; using offline demo simulation for this run.')
            try:
                emit(ProgressUpdate(step_id='assess', type='step.failed',
                    summary='Live AI unavailable or invalid. Falling back to offline demo simulation.',
                    simulation=True))
            except Exception:
                pass
            else:
                return process_offline(request, emit)
        try:
            emit(ProgressUpdate(step_id='assess', type='step.failed',
                summary='AI configuration or expert processing failed.', simulation=not live))
        except Exception:
            pass
        return RunResult(run_id=request.run_id, case_id=request.case_id,
            based_on_case_version=request.case_version, status='FAILED', simulation=not live,
            technical_error=TechnicalError(code='AI_PROCESSING_FAILED',
                message='Check backend AI configuration and provider availability.', retryable=True))
