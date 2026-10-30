"""Backend-only configuration; shell variables take precedence over root .env."""
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    mode: str
    api_key: str = field(repr=False)
    model: str = 'gpt-4o-mini'
    timeout: float = 60

    @classmethod
    def from_env(cls):
        values = {**dotenv_values(ROOT / '.env'), **os.environ}
        key = (values.get('OPENAI_API_KEY') or '').strip()
        mode = (values.get('AI_MODE') or 'auto').strip().lower()
        if mode not in {'auto', 'openai', 'offline'}:
            raise ValueError('AI_MODE must be auto, openai or offline')
        mode = ('openai' if key else 'offline') if mode == 'auto' else mode
        if mode == 'openai' and not key:
            raise ValueError('OPENAI_API_KEY is required for live mode')
        timeout = float(values.get('OPENAI_TIMEOUT_SECONDS') or '60')
        if not 0 < timeout <= 300:
            raise ValueError('Invalid OpenAI timeout')
        return cls(mode, key, (values.get('OPENAI_MODEL') or 'gpt-4o-mini').strip(), timeout)
