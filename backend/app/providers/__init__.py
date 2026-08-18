"""Provider abstraction for LLM / Image / Video / TTS.

All providers implement the same interface so the rest of the app doesn't care
which gateway is being used.

Implementations:
- LLMProvider: toapis / yijia / 302 / openai_compat / local_preview
- ImageProvider: toapis / yijia / 302 / openai_compat / local_preview
- VideoProvider: toapis / yijia / 302 / openai_compat / local_preview
- TTSProvider: edge / azure / local_preview
"""
from app.providers.base import (
    GenerationResult,
    ImageProvider,
    LLMProvider,
    ProviderError,
    ProviderRegistry,
    TTSProvider,
    VideoProvider,
)

__all__ = [
    "LLMProvider",
    "ImageProvider",
    "VideoProvider",
    "TTSProvider",
    "GenerationResult",
    "ProviderError",
    "ProviderRegistry",
]