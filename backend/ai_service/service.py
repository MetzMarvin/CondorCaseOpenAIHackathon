"""Configured System 2 entry point with explicit offline and live modes."""
from backend.contracts import ProgressUpdate, RunRequest, RunResult, TechnicalError
from backend.ai_service.settings import Settings
from backend.ai_service.workflow import ProgressCallback, run_workflow
from backend.ai_service.context import ProcessingBundle


def process_case(request: RunRequest, emit_progress: ProgressCallback) -> RunResult:
    return create_processor()(request, emit_progress)


def create_processor(*, adapters=None, extractor=None, retriever=None, settings=None, diagnostic_sink=None):
    """Bind backend-only read adapters; the returned public call stays synchronous."""
    def processor(request: RunRequest, emit_progress: ProgressCallback) -> RunResult:
        bundle = ProcessingBundle(request)
        result = _process(request, emit_progress, bundle, adapters, extractor, retriever, settings)
        if diagnostic_sink is not None:
            try:
                diagnostic_sink(bundle, result)
            except Exception:
                return RunResult(run_id=request.run_id, case_id=request.case_id,
                    based_on_case_version=request.case_version, status='FAILED', simulation=result.simulation,
                    technical_error=TechnicalError(code='DIAGNOSTIC_PERSISTENCE_FAILED',
                        message='Run diagnostics could not be stored.', retryable=True))
        return result
    return processor


def _process(request, emit_progress, bundle, adapters, extractor, retriever, settings):
    live = False
    try:
        settings = settings or Settings.from_env()
        live = settings.mode == 'openai'
        bundle.mode = settings.mode
        bundle.model = settings.model if live else None
        def progress(update):
            emit_progress(update.model_copy(update={'simulation': not live}))
        baseline = run_workflow(request, progress, bundle=bundle, adapters=adapters,
                                extractor=extractor, retriever=retriever)
        if not live:
            return baseline
        if baseline.status == 'FAILED':
            return baseline.model_copy(update={'simulation': False})
        from backend.ai_service.experts import run_experts
        return run_experts(bundle.effective_request or request, baseline, emit_progress, settings, bundle=bundle)
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
