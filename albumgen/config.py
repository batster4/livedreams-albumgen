"""Settings: config.yaml + environment (.env). Every field has a safe default."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field

PROVIDER_URLS = {
    "openrouter": "https://openrouter.ai/api/v1",
    "openai": "https://api.openai.com/v1",
}


class StageParams(BaseModel):
    """Sampling for one LLM stage."""

    temperature: float = 0.9
    top_p: float = 0.95
    max_tokens: int = 4000


class LLMConfig(BaseModel):
    provider: Literal["openrouter", "openai", "custom"] = "openrouter"
    base_url: Optional[str] = None  # required for "custom"; overrides the preset otherwise
    model: str = ""
    fallback_model: Optional[str] = None  # tried when the main model refuses or returns no JSON
    api_key_env: str = "LLM_API_KEY"
    json_mode: bool = True  # sends response_format=json_object; switched off automatically if refused
    timeout_s: float = 180
    max_retries: int = 3
    seed: Optional[int] = None
    outline: StageParams = Field(default_factory=lambda: StageParams(temperature=0.9, top_p=0.95, max_tokens=4000))
    writer: StageParams = Field(default_factory=lambda: StageParams(temperature=0.3, top_p=0.9, max_tokens=9000))
    app_name: str = "albumgen"  # sent to OpenRouter as X-Title
    app_url: Optional[str] = None  # sent to OpenRouter as HTTP-Referer

    def resolved_base_url(self) -> str:
        if self.base_url:
            return self.base_url
        if self.provider in PROVIDER_URLS:
            return PROVIDER_URLS[self.provider]
        raise ValueError("llm.base_url is required when llm.provider is 'custom'")

    def api_key(self) -> Optional[str]:
        return os.environ.get(self.api_key_env)


class AlbumConfig(BaseModel):
    reference_mode: Literal["solo", "couple"] = "solo"  # solo keeps her face most accurate
    min_age: int = 23
    max_age: int = 52
    untested: Literal["light", "off"] = "light"  # light: weak items allowed, max `max_weak_per_album`; off: never
    max_weak_per_album: int = 1
    allow_his_face: bool = False  # enables kiss on the mouth and side-view missionary
    only_families: list[str] = Field(default_factory=list)
    exclude_families: list[str] = Field(default_factory=list)
    exclude_themes: list[str] = Field(default_factory=list)
    exclude_kinks: list[str] = Field(default_factory=list)


class MemoryConfig(BaseModel):
    db_path: str = "albumgen.db"
    theme_window: int = 5  # a theme is not repeated within this many albums
    pair_window: int = 20  # location + outfit pair not repeated within this many albums
    position_window: int = 10  # positions used in these albums get a lower weight
    title_window: int = 20  # recent titles/loglines shown to the LLM as "do not repeat"
    similarity_threshold: float = 0.5  # logline keyword overlap that triggers one rewrite


class RenderConfig(BaseModel):
    base_url: str = "https://api.livedreams.ai/v1"
    api_key_env: str = "LIVEDREAMS_API_KEY"
    # A page's deadline (~5 min) counts the time it waits in the queue: keep 2 pages in flight, one album at a time.
    max_inflight: int = 2
    poll_s: float = 3.5
    job_timeout_s: float = 900
    shot1_model: str = "qwen-image-3"
    shot1_resolution: str = "2k"
    page_model: str = "canvas"
    page_resolution: str = "1k"
    aspect_ratio: str = "2:3"
    output_format: str = "jpeg"

    def api_key(self) -> Optional[str]:
        return os.environ.get(self.api_key_env)


class Config(BaseModel):
    llm: LLMConfig = Field(default_factory=LLMConfig)
    album: AlbumConfig = Field(default_factory=AlbumConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    render: RenderConfig = Field(default_factory=RenderConfig)
    data_dir: str = "data"
    out_dir: str = "out"
    root: str = "."

    @classmethod
    def load(cls, path: str | Path | None = None) -> "Config":
        path = Path(path) if path else Path("config.yaml")
        root = path.parent.resolve() if path.exists() else Path.cwd()
        load_dotenv(root / ".env")
        raw = yaml.safe_load(path.read_text()) if path.exists() else {}
        cfg = cls.model_validate(raw or {})
        cfg.root = str(root)
        return cfg

    def path(self, rel: str) -> Path:
        p = Path(rel)
        return p if p.is_absolute() else Path(self.root) / p


def load_dotenv(path: Path) -> None:
    """Minimal .env reader: KEY=value lines; existing environment wins."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)
