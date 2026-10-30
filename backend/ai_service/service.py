"""Configured System 2 entry point with explicit offline and live modes."""
from functools import partial

from backend.contracts import ProgressUpdate, RunRequest, RunResult, TechnicalError
from backend.ai_service.settings import Settings
from backend.ai_service.workflow import ProgressCallback, create_processor as create_offline_processor


def create_processor(*, adapters=None, extractor=None, retriever=None):
    """System 1 supplies authorized readers here; no business writes occur."""
    return partial(_process_case, adapters=adapters, extractor=extractor, retriever=retriever)


def process_case(request: RunRequest, emit_progress: ProgressCallback) -> RunResult:
    return _process_case(request, emit_progress)


def _process_case(request, emit_progress, *, adapters=None, extractor=None, retriever=None):
    live = False
    try:
        settings = Settings.from_env()
        live = settings.mode == 'openai'
        context = []
        process_offline = create_offline_processor(adapters=adapters, extractor=extractor,
            retriever=retriever, context_callback=lambda prepared, knowledge: context.append((prepared, knowledge)))
        if not live:
            return process_offline(request, emit_progress)
        # Code owns the supported policy, identity and financial constraints.
        baseline = process_offline(request, lambda _: None)
        if baseline.status == 'FAILED':
            return baseline.model_copy(update={'simulation': False})
        from backend.ai_service.experts import run_experts
        prepared, knowledge = context[0]
        return run_experts(prepared, baseline, emit_progress, settings, knowledge=knowledge)
    except Exception:
        try:
            emit_progress(ProgressUpdate(step_id='assess', type='step.failed',
                summary='AI configuration or expert processing failed.', simulation=not live))
        except Exception:
            pass
        return RunResult(run_id=request.run_id, case_id=request.case_id,
            based_on_case_version=request.case_version, status='FAILED', simulation=not live,
            technical_error=TechnicalError(code='AI_PROCESSING_FAILED',
                message='Check backend AI configuration and provider availability.', retryable=True))
