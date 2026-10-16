"""Rule checks for prompts (the same rules as the agent guide) + automatic everyday swaps."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .library import Library

NEGATION = re.compile(r"\b(not|no|without|never|instead|nothing)\b", re.I)
AGE = re.compile(r"\b(\d{1,2}) years old\b", re.I)
MAX_CHARS = 4000
ALLOWED = re.compile(r"\bpatient monitor\b", re.I)  # equipment, not a person


class Validator:
    def __init__(self, lib: Library, min_age: int = 18):
        self.never = lib.never_regex()
        self.swaps = lib.swaps()
        self.min_age = min_age

    def swap(self, text: str) -> str:
        for a, b in self.swaps.items():
            text = re.sub(rf"\b{re.escape(a)}\b", b, text, flags=re.I)
        # a small face with closed eyes loses the likeness: always "nearly closed"
        text = re.sub(r"\b(?<!nearly )(eyes(?: are)?) closed\b", r"\1 nearly closed", text, flags=re.I)
        text = re.sub(r"\bclosed eyes\b", "nearly closed eyes", text, flags=re.I)
        text = re.sub(r"\bcloses her eyes\b", "nearly closes her eyes", text, flags=re.I)
        return text

    def text_issues(self, text: str) -> list[str]:
        """Checks for any generated text (story fields too)."""
        text = ALLOWED.sub("", text)
        hits = sorted({m.group(0).lower() for m in self.never.finditer(text)})
        return [f"never-word: {', '.join(hits)}"] if hits else []

    def prompt_issues(self, prompt: str, shot: int) -> list[str]:
        issues = self.text_issues(prompt)
        if shot > 1:
            neg = sorted({m.group(0).lower() for m in NEGATION.finditer(prompt)})
            if neg:
                issues.append(f"negation: {', '.join(neg)}")
            if "exactly as in the reference" not in prompt and "The woman is the woman from the reference photo" not in prompt:
                issues.append("identity sentence missing")
        ages = [int(a) for a in AGE.findall(prompt)]
        if shot == 1 and not ages:
            issues.append("numeric age missing")
        if any(a < self.min_age for a in ages):
            issues.append(f"age below {self.min_age}")
        if len(prompt) > MAX_CHARS:
            issues.append(f"too long ({len(prompt)} > {MAX_CHARS})")
        return issues

    def album_issues(self, requests: list[dict]) -> dict[int, list[str]]:
        out: dict[int, list[str]] = {}
        for r in requests:
            if "prompt" not in r:
                continue
            issues = self.prompt_issues(r["prompt"], int(r["shot"]))
            if int(r["shot"]) == 1 and r.get("model") != "qwen-image-3":
                issues.append("shot 1 should be qwen-image-3 text-to-image")
            if int(r["shot"]) > 1:
                imgs = r.get("params", {}).get("images")
                if r.get("model") != "canvas" or not imgs:
                    issues.append("page should be canvas with images=[{job_id of shot 1}]")
            if issues:
                out[int(r["shot"])] = issues
        return out


def check_file(lib: Library, path: str | Path, min_age: int = 18) -> dict[int, list[str]]:
    data: Any = json.loads(Path(path).read_text())
    requests = data["requests"] if isinstance(data, dict) else data
    return Validator(lib, min_age).album_issues(requests)
