"""Provider registry initialization.

Imports all built-in providers and registers them.
Called once at app startup via `register_all_providers()`.
"""
from __future__ import annotations

from app.providers.base import ProviderRegistry
from app.providers.local_preview import (
    LocalPreviewImageProvider,
    LocalPreviewLLMProvider,
    LocalPreviewTTSProvider,
    LocalPreviewVideoProvider,
)
from app.providers.openai_compat import (
    OpenAICompatImageProvider,
    OpenAICompatLLMProvider,
    OpenAICompatVideoProvider,
)
from app.providers.toapis import ToapisImageProvider, ToapisLLMProvider, ToapisVideoProvider
from app.providers.yijia import YijiaImageProvider, YijiaVideoProvider


def register_all_providers() -> None:
    """Idempotent: registers all built-in providers into the static registry."""
    # LLM
    ProviderRegistry.register_llm("toapis", ToapisLLMProvider)
    ProviderRegistry.register_llm("yijia", ToapisLLMProvider)  # yijia reuses toapis client
    ProviderRegistry.register_llm("302", ToapisLLMProvider)  # 302 reuses toapis client
    ProviderRegistry.register_llm("openai_compat", OpenAICompatLLMProvider)
    ProviderRegistry.register_llm("local_preview", LocalPreviewLLMProvider)

    # Image
    ProviderRegistry.register_image("toapis", ToapisImageProvider)
    ProviderRegistry.register_image("yijia", YijiaImageProvider)
    ProviderRegistry.register_image("302", ToapisImageProvider)
    ProviderRegistry.register_image("openai_compat", OpenAICompatImageProvider)
    ProviderRegistry.register_image("local_preview", LocalPreviewImageProvider)

    # Video
    ProviderRegistry.register_video("toapis", ToapisVideoProvider)
    ProviderRegistry.register_video("yijia", YijiaVideoProvider)
    ProviderRegistry.register_video("302", ToapisVideoProvider)
    ProviderRegistry.register_video("openai_compat", OpenAICompatVideoProvider)
    ProviderRegistry.register_video("local_preview", LocalPreviewVideoProvider)

    # TTS
    ProviderRegistry.register_tts("edge", LocalPreviewTTSProvider)  # placeholder; real edge impl in edge.py
    ProviderRegistry.register_tts("azure", LocalPreviewTTSProvider)
    ProviderRegistry.register_tts("local_preview", LocalPreviewTTSProvider)