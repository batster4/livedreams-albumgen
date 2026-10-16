"""make_album(): sample → story → page texts → validate → save files and memory."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .compose import shot1_prompt
from .config import Config
from .library import Library
from .memory import Memory
from .sampler import Plan, Sampler
from .story import default_outline, make_outline
from .validate import Validator
from .writer import write_pages


@dataclass
class AlbumResult:
    album_id: str
    dir: Path
    requests: list[dict]
    plan: Plan
    outline: dict
    sources: dict[int, str]
    issues: dict[int, list[str]] = field(default_factory=dict)
    llm_calls: int = 0


def requests_for(plan: Plan, cfg: Config, prompts: dict[int, str], shot1: str) -> list[dict]:
    r = cfg.render
    out = [{
        "shot": 1, "model": r.shot1_model,
        "params": {"aspect_ratio": r.aspect_ratio, "resolution": r.shot1_resolution, "output_format": r.output_format,
                   "enhance_prompt": False},
        "prompt": shot1, "changes": [],
    }]
    for p in plan.pages:
        out.append({
            "shot": p.shot, "model": r.page_model,
            "params": {"aspect_ratio": r.aspect_ratio, "resolution": r.page_resolution, "output_format": r.output_format,
                       "images": [{"job_id": "<shot 1 job id>"}]},
            "prompt": prompts[p.shot], "changes": [],
        })
    return out


def story_md(plan: Plan, lib: Library, outline: dict, requests: list[dict], sources: dict[int, str]) -> str:
    c = plan.character
    by_shot = {int(x["shot"]): x for x in outline.get("pages", [])}
    lines = [
        f"# {outline.get('title', plan.theme['title'])}", "",
        f"*{outline.get('logline', plan.theme['hook'])}*", "",
        f"- Album: `{plan.album_id}` · theme `{plan.theme['id']}` ({plan.theme['family']}) · arc `{plan.arc_id}` · "
        f"shot 1: {plan.reference_mode}",
        f"- Her: {c.age}, {c.ethnicity}, {c.hair}, {c.figure_short}{', ' + c.extra if c.extra else ''}",
        (f"- Her partner: {plan.partner.age}, {plan.partner.ethnicity}, {plan.partner.hair}, {plan.partner.figure_short}"
         if plan.partner else f"- Him: {plan.man.face_sentence if plan.reference_mode == 'couple' else plan.man.sentence}"),
        f"- Place: {plan.location['phrase']} · light: {plan.location['light']}",
        (f"- Outfits: she wears {plan.her_outfit['phrase']}; her partner wears {(plan.partner_outfit or plan.her_outfit)['phrase']}"
         if plan.partner else f"- Outfits: she wears {plan.her_outfit['phrase']}; he wears {plan.his_outfit['phrase']}"), "",
        "| Shot | Slot | Position | Status | She / He | Beat | Made by |", "|---|---|---|---|---|---|---|",
        f"| 1 | reference | {plan.reference_mode} shot 1 | — | outfit | {plan.theme['hook']} | template |",
    ]
    for p in plan.pages:
        pos = lib.positions[p.position_id]
        beat = by_shot.get(p.shot, {}).get("beat", "").replace("|", "/")
        lines.append(f"| {p.shot} | {p.slot} | `{p.position_id}` | {pos.get('status', '')} | {p.her_stage} / {p.him_stage} | {beat} | {sources.get(p.shot, '')} |")
    lines += ["", "## Prompts", ""]
    for r in requests:
        lines += [f"### Shot {r['shot']} · {r['model']}", "", "```text", r["prompt"], "```", ""]
    return "\n".join(lines)


def make_album(cfg: Config, *, theme: Optional[str] = None, arc: Optional[str] = None, mode: Optional[str] = None,
               seed: Optional[int] = None, llm=None, dry_run: bool = False, save: bool = True,
               library: Optional[Library] = None, memory: Optional[Memory] = None) -> AlbumResult:
    lib = library or Library.load(cfg.path(cfg.data_dir))
    mem = memory or Memory(cfg.path(cfg.memory.db_path))
    seed = seed if seed is not None else random.SystemRandom().randrange(2**31)
    rng = random.Random(seed)
    v = Validator(lib, cfg.album.min_age)
    plan = Sampler(lib, mem, cfg.album, cfg.memory, rng).plan(theme_id=theme, arc_id=arc, mode=mode, seed=seed)

    if dry_run:
        llm = None
    if llm is None and not dry_run:
        from .llm import make_llm

        llm = make_llm(cfg.llm)  # None without a model or key: recipe text
    log_start = len(getattr(llm, "log", None) or [])  # one LLM object serves a whole batch: keep this album's calls
    recent = mem.recent_titles(cfg.memory.title_window)
    outline = make_outline(llm, plan, lib, cfg, v, recent) if llm is not None else default_outline(plan)
    prompts, sources = write_pages(llm, plan, lib, outline, cfg, v)
    shot1 = v.swap(shot1_prompt(plan))
    requests = requests_for(plan, cfg, prompts, shot1)
    issues = v.album_issues(requests)

    out_dir = cfg.path(cfg.out_dir) / plan.album_id
    if save:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "album.json").write_text(json.dumps(requests, indent=2, ensure_ascii=False))
        (out_dir / "story.md").write_text(story_md(plan, lib, outline, requests, sources))
        (out_dir / "plan.json").write_text(json.dumps({"plan": plan.to_dict(), "outline": outline, "sources": sources,
                                                       "issues": issues,
                                                       "llm": (getattr(llm, "log", None) or [])[log_start:]},
                                                      indent=2, ensure_ascii=False, default=str))
        mem.save_album({
            "album_id": plan.album_id, "seed": seed, "theme_id": plan.theme["id"], "family": plan.theme["family"],
            "arc_id": plan.arc_id, "location_id": plan.location["id"], "her_outfit_id": plan.her_outfit["id"],
            "his_outfit_id": plan.his_outfit["id"], "reference_mode": plan.reference_mode,
            "character_fp": plan.character.fingerprint,
            "character": {**plan.to_dict()["character"], "partner": plan.to_dict().get("partner")},
            "positions": [p.position_id for p in plan.pages], "title": outline.get("title"),
            "logline": outline.get("logline"), "llm_model": getattr(llm, "model_name", None) if llm else "dry-run",
        })
    return AlbumResult(album_id=plan.album_id, dir=out_dir, requests=requests, plan=plan, outline=outline,
                       sources=sources, issues=issues, llm_calls=getattr(llm, "calls", 0) if llm else 0)
