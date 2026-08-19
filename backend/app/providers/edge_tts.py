"""Edge TTS provider — free, CPU-only, no install (uses Microsoft Edge online TTS).

Default voice: zh-CN-YunyangNeural (Chinese male, news style).
Other voices: en-US-AriaNeural, ja-JP-NanamiNeural, etc.
"""
from __future__ import annotations

import asyncio
import re

import edge_tts
from app.providers.base import GenerationResult, ProviderError, TTSProvider, UserProviderConfig


class EdgeTTSProvider(TTSProvider):
    name = "edge"

    DEFAULT_VOICE = "zh-CN-YunyangNeural"

    # Strip chars that edge-tts / SSML doesn't render well
    _STRIP_RE = re.compile(r"[#*`\[\]<>]+")

    def __init__(self, **kwargs):
        pass

    async def synthesize(
        self,
        *,
        text: str,
        voice: str = "",
        output_path,
        config: UserProviderConfig | None = None,
    ) -> GenerationResult:
        """Synthesize text to a WAV/MP3 file via edge-tts."""
        voice = voice or self.DEFAULT_VOICE
        text = self._STRIP_RE.sub("", text).strip()
        if not text:
            return GenerationResult(success=False, error="Empty text after cleanup")

        # Default to mp3 for smaller files; the writer will decide.
        communicate = edge_tts.Communicate(text=text, voice=voice)
        output_path = str(output_path)
        try:
            await communicate.save(output_path)
        except Exception as e:
            # Fallback: try without rate/volume tweaks
            try:
                communicate = edge_tts.Communicate(text=text, voice=voice)
                await communicate.save(output_path)
            except Exception as e2:
                raise ProviderError(self.name, f"edge-tts failed: {e2}") from e

        import os
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            return GenerationResult(success=False, error="edge-tts produced empty file")

        # Estimate duration from file size (mp3 ~16kbps typical)
        size_kb = os.path.getsize(output_path) / 1024
        approx_seconds = max(1.0, size_kb * 1024 * 8 / 16000)

        return GenerationResult(
            success=True,
            output_path=output_path,
            metadata={"voice": voice, "approx_seconds": approx_seconds, "size_bytes": os.path.getsize(output_path)},
            cost_credits=2,
        )