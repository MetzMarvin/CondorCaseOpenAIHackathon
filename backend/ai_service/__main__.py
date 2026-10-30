"""Run the System 2 contract demonstration without an HTTP server or model."""
import json
from backend.ai_service import process_case
from backend.ai_service.fixtures import demo_request

for scenario in ('clear', 'missing', 'reply', 'serious', 'unsupported'):
    progress = []
    result = process_case(demo_request(scenario), progress.append)
    print(json.dumps({'scenario': scenario, 'progress': [p.model_dump(mode='json', by_alias=True) for p in progress],
                      'result': result.model_dump(mode='json', by_alias=True)}, ensure_ascii=False))
