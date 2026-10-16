"""One client for any OpenAI-compatible chat API (OpenRouter, OpenAI, vLLM, LM Studio, ...).
Asks for JSON, recovers JSON from chatty answers, retries once on bad JSON, and falls back to a second
model when the first one refuses."""

from __future__ import annotations

import json
import time
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Protocol

from .config import LLMConfig, StageParams

REFUSAL = re.compile(
    r"\b(I can(?:'|no)t (?:help|assist|create|write|provide)|I'm (?:sorry|unable)|I am (?:sorry|unable)|"
    r"I won't|against (?:my|the) (?:guidelines|policy))", re.I)


class LLMError(RuntimeError):
    pass


class ChatModel(Protocol):
    model_name: str

    def json(self, system: str, user: str, stage: StageParams, name: str) -> Any: ...


def extract_json(text: str) -> Any:
    """Parse the first JSON object/array in a reply (handles ```json fences and text around it)."""
    text = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    starts = [i for i in (text.find("{"), text.find("[")) if i >= 0]
    if not starts:
        raise ValueError("no JSON in the reply")
    decoder = json.JSONDecoder()
    obj, _ = decoder.raw_decode(text[min(starts):])
    return obj


@dataclass
class LLM:
    cfg: LLMConfig
    calls: int = 0
    log: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        from openai import OpenAI  # imported here so --dry-run works without the package configured

        key = self.cfg.api_key()
        if not key:
            raise LLMError(f"set {self.cfg.api_key_env} (see .env.example)")
        if not self.cfg.model:
            raise LLMError("set llm.model in config.yaml")
        headers = {}
        if self.cfg.provider == "openrouter":
            headers["X-Title"] = self.cfg.app_name
            if self.cfg.app_url:
                headers["HTTP-Referer"] = self.cfg.app_url
        self.client = OpenAI(base_url=self.cfg.resolved_base_url(), api_key=key, default_headers=headers or None,
                             timeout=self.cfg.timeout_s, max_retries=self.cfg.max_retries)
        self._json_mode = self.cfg.json_mode

    @property
    def model_name(self) -> str:
        return self.cfg.model

    def _complete(self, model: str, messages: list[dict], stage: StageParams) -> str:
        from openai import BadRequestError

        kw: dict[str, Any] = dict(model=model, messages=messages, temperature=stage.temperature, top_p=stage.top_p)
        if self.cfg.provider == "openai":
            kw["max_completion_tokens"] = stage.max_tokens
        else:
            kw["max_tokens"] = stage.max_tokens
        if self.cfg.seed is not None:
            kw["seed"] = self.cfg.seed
        if self._json_mode:
            kw["response_format"] = {"type": "json_object"}
        try:
            resp = self.client.chat.completions.create(**kw)
        except BadRequestError as e:
            if self._json_mode and "response_format" in str(e).lower():
                self._json_mode = False  # this endpoint/model has no JSON mode: ask in the prompt instead
                kw.pop("response_format", None)
                resp = self.client.chat.completions.create(**kw)
            else:
                raise
        self.calls += 1
        return resp.choices[0].message.content or ""

    def json(self, system: str, user: str, stage: StageParams, name: str) -> Any:
        models = [self.cfg.model] + ([self.cfg.fallback_model] if self.cfg.fallback_model else [])
        last = ""
        for model in models:
            messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
            for attempt in range(2):
                t0 = time.monotonic()
                text = self._complete(model, messages, stage)
                last = text
                self.log.append({"stage": name, "model": model, "attempt": attempt + 1, "chars": len(text),
                                 "seconds": round(time.monotonic() - t0, 1)})
                try:
                    return extract_json(text)
                except ValueError:
                    if REFUSAL.search(text[:400]):
                        break  # refused: try the fallback model
                    messages += [{"role": "assistant", "content": text},
                                 {"role": "user", "content": "Return only the JSON object described above, nothing else."}]
        raise LLMError(f"{name}: no usable JSON from {models}; last reply starts: {last[:200]!r}")


@dataclass
class FakeLLM:
    """For tests and offline runs: `responder(name, payload) -> dict`."""

    responder: Callable[[str, dict], Any]
    model_name: str = "fake"
    calls: int = 0

    def json(self, system: str, user: str, stage: StageParams, name: str) -> Any:
        self.calls += 1
        return self.responder(name, json.loads(user))


def make_llm(cfg: LLMConfig) -> Optional[LLM]:
    """The configured LLM, or None when no model or key is set (albums are then written from the tested recipes)."""
    if not cfg.model or not cfg.api_key():
        return None
    return LLM(cfg)
