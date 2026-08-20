"""Provider registry initialization.

Imports all built-in providers and registers them.
Called once at app startup via `register_all_providers()`.
"""
from __future__ import annotations

from app.providers.base import ProviderRegistry
from app.core.config import settings
from app.providers.edge_tts import EdgeTTSProvider
from app.providers.geeknow_image import GeeknowImageProvider
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


def _make_geeknow_provider(klass):
    """Pre-configure geeknow LLM/Image/Video with platform key."""

    class _GeekNowLLM(klass):
        def __init__(self, **kwargs):
            super().__init__(
                api_key=settings.platform_geeknow_api_key,
                base_url=settings.platform_geeknow_base_url,
                **kwargs,
            )

    _GeekNowLLM.__name__ = f"GeekNow{klass.__name__}"
    return _GeekNowLLM


def register_all_providers() -> None:
    """Idempotent: registers all built-in providers into the static registry."""
    # LLM
    ProviderRegistry.register_llm("toapis", ToapisLLMProvider)
    ProviderRegistry.register_llm("yijia", ToapisLLMProvider)  # yijia reuses toapis client
    ProviderRegistry.register_llm("302", ToapisLLMProvider)  # 302 reuses toapis client
    ProviderRegistry.register_llm("openai_compat", OpenAICompatLLMProvider)
    ProviderRegistry.register_llm("geeknow", _make_geeknow_provider(OpenAICompatLLMProvider))
    ProviderRegistry.register_llm("local_preview", LocalPreviewLLMProvider)

    # Image
    ProviderRegistry.register_image("toapis", ToapisImageProvider)
    ProviderRegistry.register_image("yijia", YijiaImageProvider)
    ProviderRegistry.register_image("302", ToapisImageProvider)
    ProviderRegistry.register_image("openai_compat", OpenAICompatImageProvider)
    ProviderRegistry.register_image("geeknow", _make_geeknow_provider(OpenAICompatImageProvider))
    ProviderRegistry.register_image("geeknow_image", GeeknowImageProvider)  # 用 images/generations 端点
    ProviderRegistry.register_image("local_preview", LocalPreviewImageProvider)

    # Video
    ProviderRegistry.register_video("toapis", ToapisVideoProvider)
    ProviderRegistry.register_video("yijia", YijiaVideoProvider)
    ProviderRegistry.register_video("302", ToapisVideoProvider)
    ProviderRegistry.register_video("openai_compat", OpenAICompatVideoProvider)
    ProviderRegistry.register_video("geeknow", _make_geeknow_provider(OpenAICompatVideoProvider))
    ProviderRegistry.register_video("local_preview", LocalPreviewVideoProvider)

    # TTS
    ProviderRegistry.register_tts("edge", EdgeTTSProvider)
    ProviderRegistry.register_tts("azure", LocalPreviewTTSProvider)
    ProviderRegistry.register_tts("local_preview", LocalPreviewTTSProvider)