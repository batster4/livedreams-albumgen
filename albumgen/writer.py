"""Stage 3: the LLM writes two fields per page: her pose (a variation of the proven pose hint, adapted to the place
and the story) and her emotion. Everything that decides anatomy, clothing and the man is written by code
(compose.py). A field that breaks the rules is asked again once, then replaced by the recipe text."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .compose import assemble, fallback_fields, fill, her_clothing, man_part
from .config import Config
from .library import Library, emotion_issues
from .sampler import Plan
from .story import DEFAULT_EMOTION
from .validate import Validator

# words that belong to code-owned sentences; the LLM must not write them into her pose or emotion
OFF_LIMITS = re.compile(
    r"\b(penis|cock|shaft|semen|cum|vagina|vulva|clitoris|anus|inside her|naked|nude|wears?|wearing|"
    r"dressed|bra|bralette|thong|panties|lingerie|dress|skirt|shirt|corset|stockings?|robe|bikini|swimsuit|trousers|"
    r"jeans|uniform)\b", re.I)
POSTURE = [("kneel", r"kneel"), ("lie", r"\blie|lies|lying"), ("sit", r"\bsit|sits|sitting|seated"),
           ("stand", r"\bstand|stands|standing"), ("all fours", r"all fours"), ("straddle", r"straddl|astride"),
           ("bend", r"\bbend|bends|bent"), ("recline", r"reclin")]


def _postures(text: str) -> set[str]:
    return {name for name, rx in POSTURE if re.search(rx, text, re.I)}


def brief(plan: Plan, lib: Library, outline: dict, only: set[int] | None = None,
          fixes: dict[int, list[str]] | None = None) -> dict[str, Any]:
    by_shot = {int(x["shot"]): x for x in outline.get("pages", [])}
    pages = []
    for p in plan.pages:
        if only is not None and p.shot not in only:
            continue
        pos = lib.positions[p.position_id]
        o = by_shot.get(p.shot, {})
        item = {
            "shot": p.shot, "slot": p.slot,
            "camera (fixed)": fill(pos.get("camera", ""), plan),
            "her clothing (fixed)": her_clothing(plan, p.her_stage, pos),
            "act (fixed)": fill(pos.get("act", ""), plan),
            "man (fixed)": man_part(plan, p, pos),
            "POSE HINT": fill(str(pos.get("scene") or pos.get("her", "")), plan),
            "pose written by code": code_owned_pose(pos),
            "beat": o.get("beat", ""), "emotion idea": o.get("emotion") or DEFAULT_EMOTION[p.slot],
            "detail": o.get("detail", ""),
        }
        if fixes and p.shot in fixes:
            item["fix_this"] = fixes[p.shot]
        pages.append(item)
    return {
        "her_look": f"{plan.character.age}-year-old {plan.character.ethnicity} woman, {plan.character.hair}",
        "location": f"{plan.location['phrase']} ({plan.location['props']})",
        "pages": pages,
    }


def _parse(out: Any) -> dict[int, dict]:
    if not isinstance(out, dict) or not isinstance(out.get("pages"), list):
        return {}
    res = {}
    for x in out["pages"]:
        if isinstance(x, dict) and str(x.get("shot", "")).isdigit():
            res[int(x["shot"])] = {k: str(x.get(k) or "").strip() for k in ("her", "emotion")}
    return res


def code_owned_pose(pos: dict) -> bool:
    """Story beats, two-women poses and poses that name clothing or his body (e.g. unbuttoning his shirt) are written
    by code; the LLM only adds the emotion there."""
    return bool(pos.get("beat") or pos.get("cast") == "ff" or OFF_LIMITS.search(str(pos.get("her", ""))))


def field_issues(plan: Plan, lib: Library, shot: int, f: dict) -> list[str]:
    page = next(p for p in plan.pages if p.shot == shot)
    pos = lib.positions[page.position_id]
    issues = []
    her, emo = f.get("her", ""), f.get("emotion", "")
    if code_owned_pose(pos):
        return emotion_issues(lib, page.slot, emo)
    if not her:
        issues.append("'her' is empty")
    for name, text in (("her", her), ("emotion", emo)):
        bad = sorted({m.group(0).lower() for m in OFF_LIMITS.finditer(text)})
        if bad:
            issues.append(f"'{name}' must describe only her own pose, hands and face; remove: {', '.join(bad)}")
    issues += emotion_issues(lib, page.slot, emo)
    issues += [i.replace("emotion", "'her'") for i in emotion_issues(lib, page.slot, her)]
    need = _postures(str(pos.get("her", "")))
    if her and need and not (_postures(her) & need):
        issues.append(f"'her' must keep the body position of the POSE HINT ({', '.join(sorted(need))})")
    if len(her) > 380 or len(emo) > 200:
        issues.append("too long: 'her' max 380 characters, 'emotion' max 200")
    return issues


def write_pages(llm, plan: Plan, lib: Library, outline: dict, cfg: Config, v: Validator) -> tuple[dict[int, str], dict[int, str]]:
    """Returns ({shot: prompt}, {shot: how it was made}) for shots 2..16."""
    system = (Path(cfg.path(cfg.data_dir)) / "prompting" / "writer_system.md").read_text()
    fields: dict[int, dict] = {}
    llm_error = ""
    if llm is not None:
        try:
            fields = _parse(llm.json(system, json.dumps(brief(plan, lib, outline), ensure_ascii=False), cfg.llm.writer, "writer"))
        except Exception as e:  # refusal, no JSON, network: every page falls back to its tested recipe
            llm_error = str(e)[:120]
    prompts: dict[int, str] = {}
    source: dict[int, str] = {}
    failing: dict[int, list[str]] = {}

    def try_page(shot: int, f: dict | None) -> list[str]:
        if f is None:
            return ["page missing from the reply"]
        f = {k: v.swap(val) for k, val in f.items()}
        issues = field_issues(plan, lib, shot, f)
        if issues:
            return issues
        page = next(p for p in plan.pages if p.shot == shot)
        if code_owned_pose(lib.positions[page.position_id]):
            f["her"] = ""  # the recipe pose is used
        prompt = assemble(plan, lib, page, f)
        issues = v.prompt_issues(prompt, shot)
        if not issues:
            prompts[shot] = prompt
        return issues

    for p in plan.pages:
        issues = try_page(p.shot, fields.get(p.shot))
        if issues:
            failing[p.shot] = issues
        else:
            source[p.shot] = "llm"
    if failing and llm is not None and fields:
        try:
            repaired = _parse(llm.json(system, json.dumps(brief(plan, lib, outline, set(failing), failing), ensure_ascii=False),
                                       cfg.llm.writer, "writer-repair"))
        except Exception:
            repaired = {}
        for shot in list(failing):
            if not try_page(shot, repaired.get(shot)):
                source[shot] = "llm-repaired"
                del failing[shot]
    by_shot = {int(x["shot"]): x for x in outline.get("pages", [])}
    for shot, why in failing.items():  # the recipe text is always valid
        page = next(p for p in plan.pages if p.shot == shot)
        emo = (fields.get(shot) or {}).get("emotion", "")
        if not emo or OFF_LIMITS.search(emo):
            emo = by_shot.get(shot, {}).get("emotion") or DEFAULT_EMOTION[page.slot]
        f = fallback_fields(plan, lib, page, v.swap(emo))
        prompts[shot] = assemble(plan, lib, page, f)
        source[shot] = "recipe" + (f" (llm: {llm_error or why[0]})" if llm is not None else "")
    return prompts, source
