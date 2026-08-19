"""LocalPreview providers — zero-cost placeholders for demo / fallback.

- LLM: returns a fixed structured script template (no network, no model)
- Image: returns a placeholder URL (Picsum)
- Video: synthesizes a real MP4 with ffmpeg (title + keyword chips, no AI)
- TTS: returns a silent placeholder audio
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.providers.base import (
    GenerationResult,
    ImageProvider,
    LLMProvider,
    ProviderError,
    TTSProvider,
    UserProviderConfig,
    VideoProvider,
)


# ===== LLM =====

# Fixed script template, filled by the user's project context.
# JSON braces are doubled {{ }} so .format() only sees {title} etc.
SCRIPT_TEMPLATE = """{{
  "logline": "{title} — 一位{主角}在{场景}中{核心冲突}",
  "style": "{style}",
  "characters": [
    {{"name": "主角", "description": "一位{年龄}岁的{身份},性格{性格1}但内心{性格2}", "appearance": "穿着{服饰},表情{表情1}"}},
    {{"name": "配角", "description": "{配角类型},推动剧情的关键人物", "appearance": "与主角形成鲜明对比"}}
  ],
  "assets": [
    {{"type": "scene", "name": "主场景", "description": "{场景}的空间,光线{光线}"}},
    {{"type": "prop", "name": "关键道具", "description": "推动剧情的物品"}}
  ],
  "episodes": [
    {{"index": 1, "title": "开篇", "outline": "介绍主角与背景,埋下悬念"}},
    {{"index": 2, "title": "冲突", "outline": "主角遇到挑战,内心挣扎"}},
    {{"index": 3, "title": "收束", "outline": "解决问题,留下钩子"}}
  ]
}}"""


# Fixed storyboard template for local_preview fallback.
# Used when LLM providers fail (no key, network down, etc.).
LOCAL_STORYBOARD_TEMPLATE = """{{
  "shots": [
    {{"index": 1, "title": "开篇", "characters": ["主角"], "prompt": "A cinematic medium shot of {char} standing in {scene}, looking ahead with determination. Soft natural light, depth of field, 35mm film look.", "narration": "这是{title}的开始,{char}踏上了新的旅程。", "duration": 5}},
    {{"index": 2, "title": "冲突", "characters": ["主角", "配角"], "prompt": "Over-the-shoulder two-shot of {char} and another character in tense conversation. Slightly low angle, dramatic lighting.", "narration": "面对突如其来的挑战,{char}必须做出选择。", "duration": 5}},
    {{"index": 3, "title": "转折", "characters": ["主角"], "prompt": "Close-up portrait of {char}'s face showing emotional change. Warm golden hour light, shallow depth of field.", "narration": "内心翻涌,决定已下,故事将走向新的方向。", "duration": 5}}
  ]
}}"""


# ===== Script generation =====


def _build_local_script(title: str = "示例短剧") -> str:
    return SCRIPT_TEMPLATE.format(
        title=title,
        主角="年轻人",
        场景="现代都市",
        核心冲突="追寻自我价值",
        style="现代都市",
        年龄="25",
        身份="上班族",
        性格1="内敛",
        性格2="渴望突破",
        服饰="休闲商务",
        表情1="坚毅",
        配角类型="亦敌亦友的同事",
        光线="柔和自然光",
    )


def _build_local_storyboard(episode_title: str, episode_outline: str, character_names: list[str]) -> str:
    """Render a storyboard JSON for a fallback episode."""
    char = character_names[0] if character_names else "主角"
    scene = "现代都市的街道" if "都" in (episode_outline or "") else "指定场景"
    return LOCAL_STORYBOARD_TEMPLATE.format(
        title=episode_title or "本集",
        char=char,
        scene=scene,
    )


# ===== Providers =====


class LocalPreviewLLMProvider(LLMProvider):
    name = "local_preview"

    def __init__(self, **kwargs):
        pass

    async def generate_text(
        self,
        *,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        config: UserProviderConfig | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        response_format: dict | None = None,
    ) -> GenerationResult:
        # Detect whether this is a storyboard call (by system prompt content)
        if system and "分镜" in system:
            # Extract episode context from prompt
            m_title = re.search(r"集标题[:：]\s*(.+)", prompt)
            m_outline = re.search(r"集概要[:：]\s*(.+)", prompt)
            m_chars = re.search(r"可用角色[:：]\s*(.+)", prompt)
            chars = [c.strip() for c in (m_chars.group(1) if m_chars else "").split("、") if c.strip()]
            text = _build_local_storyboard(
                episode_title=m_title.group(1).strip() if m_title else "",
                episode_outline=m_outline.group(1).strip() if m_outline else "",
                character_names=chars,
            )
        else:
            m = re.search(r"主题[::]\s*(.+?)(?:[\n,。]|$)", prompt)
            title = m.group(1).strip() if m else "示例短剧"
            text = _build_local_script(title)

        return GenerationResult(
            success=True,
            text=text,
            metadata={"mode": "preview", "note": "Local preview — not real AI"},
            cost_credits=0,
        )


# ===== Image =====

class LocalPreviewImageProvider(ImageProvider):
    name = "local_preview"

    def __init__(self, **kwargs):
        pass

    async def generate_image(
        self,
        *,
        prompt: str,
        model: str | None = None,
        config: UserProviderConfig | None = None,
        size: str = "1024x1024",
        reference_images: list[str] | None = None,
    ) -> GenerationResult:
        # Use Picsum with deterministic seed derived from prompt
        seed = abs(hash(prompt)) % 1000
        w, h = (768, 432) if size == "16:9" else (1024, 1024)
        url = f"https://picsum.photos/seed/preview{seed}/{w}/{h}"
        return GenerationResult(
            success=True,
            output_url=url,
            metadata={"mode": "preview", "note": "Placeholder image"},
            cost_credits=0,
        )


# ===== Video =====

class LocalPreviewVideoProvider(VideoProvider):
    name = "local_preview"

    def __init__(self, **kwargs):
        pass

    async def generate_video(
        self,
        *,
        prompt: str,
        first_frame: str | None = None,
        duration: float = 5.0,
        aspect_ratio: str = "16:9",
        model: str | None = None,
        config: UserProviderConfig | None = None,
    ) -> GenerationResult:
        """Render a real MP4 with title + keywords using ffmpeg."""
        out_path = Path(tempfile.gettempdir()) / f"preview_video_{abs(hash(prompt)) % 100000}.mp4"
        ok = _render_ffmpeg(prompt, out_path, duration, aspect_ratio)
        if not ok:
            return GenerationResult(
                success=False,
                error="Local preview video render failed (install ffmpeg)",
            )
        return GenerationResult(
            success=True,
            output_path=out_path,
            output_url=f"file://{out_path}",
            metadata={"mode": "preview", "duration": duration, "path": str(out_path)},
            cost_credits=0,
        )


def _find_ffmpeg() -> str | None:
    candidates = [
        Path("./tools/ffmpeg/ffmpeg.exe") if os.name == "nt" else Path("./tools/ffmpeg/ffmpeg"),
        Path("./tools/ffmpeg/ffmpeg"),
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return shutil.which("ffmpeg")


def _extract_keywords(prompt: str, max_kw: int = 3) -> list[str]:
    parts = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z]{4,}", prompt)
    seen, out = set(), []
    for p in parts:
        if p.lower() in seen:
            continue
        seen.add(p.lower())
        out.append(p)
        if len(out) >= max_kw:
            break
    return out


def _render_ffmpeg(prompt: str, out_path: Path, duration: float, aspect: str) -> bool:
    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        return False
    if aspect == "16:9":
        w, h = 768, 432
    elif aspect == "9:16":
        w, h = 432, 768
    else:
        w, h = 768, 768

    src = f"color=c=0x1e293b:s={w}x{h}:d={duration}:r=24"
    safe_title = "预览镜头"
    chain = src + (
        f",drawtext=text='{safe_title}':fontfile=/Windows/Fonts/msyh.ttc:"
        f"x=24:y=24:fontsize=28:fontcolor=white:"
        f"box=1:boxcolor=0x667eea@0.85:boxborderw=10"
    )
    kws = _extract_keywords(prompt) or ["预览占位"]
    y = h - 60
    for chip in kws:
        chip_safe = chip.replace(":", "\\:").replace("'", "\\'")
        chain += (
            f",drawtext=text='{chip_safe}':fontfile=/Windows/Fonts/msyh.ttc:"
            f"x=24:y={y}:fontsize=18:fontcolor=white:"
            f"box=1:boxcolor=0x000000@0.55:boxborderw=8"
        )
        y += 36
    chain += ",format=yuv420p"

    cmd = [
        ffmpeg, "-y", "-f", "lavfi", "-i", chain,
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", str(out_path),
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if r.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0:
            return True
        # Retry without fontfile (Linux fallback)
        chain2 = src + (
            f",drawtext=text='{safe_title}':x=24:y=24:fontsize=28:fontcolor=white:"
            f"box=1:boxcolor=0x667eea@0.85:boxborderw=10"
        )
        y = h - 60
        for chip in kws:
            chip_safe = chip.replace(":", "\\:").replace("'", "\\'")
            chain2 += (
                f",drawtext=text='{chip_safe}':x=24:y={y}:fontsize=18:fontcolor=white:"
                f"box=1:boxcolor=0x000000@0.55:boxborderw=8"
            )
            y += 36
        chain2 += ",format=yuv420p"
        cmd2 = [ffmpeg, "-y", "-f", "lavfi", "-i", chain2, "-c:v", "libx264", "-preset", "ultrafast",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_path)]
        r2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=60)
        return r2.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0
    except Exception:
        return False


# ===== TTS =====

class LocalPreviewTTSProvider(TTSProvider):
    name = "local_preview"

    def __init__(self, **kwargs):
        pass

    async def synthesize(
        self,
        *,
        text: str,
        voice: str = "zh-CN-YunyangNeural",
        output_path: Path,
        config: UserProviderConfig | None = None,
    ) -> GenerationResult:
        """Generate a silent placeholder WAV (no real TTS — just makes the flow runnable).

        For real TTS, use the edge provider (added in v2.1).
        """
        try:
            import wave

            output_path.parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(output_path), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(24000)
                # 1 second of silence per 5 chars of text (rough)
                duration_s = max(1.0, len(text) / 5.0)
                w.writeframes(b"\x00\x00" * int(24000 * duration_s))
            return GenerationResult(
                success=True,
                output_path=output_path,
                metadata={"mode": "preview", "duration_s": duration_s},
                cost_credits=0,
            )
        except Exception as e:
            return GenerationResult(success=False, error=str(e))