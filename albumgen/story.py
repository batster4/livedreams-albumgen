"""Stage 2: the LLM writes the story (title, logline, a beat and an emotion per page) inside the sampled
skeleton. It may only swap a page's position for one of that page's alternatives."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from .config import Config
from .library import Library, emotion_issues
from .sampler import Plan
from .validate import Validator

DEFAULT_EMOTION = {
    "intro": "She gives him a slow, flirtatious look, her lips slightly parted",
    "tease": "She looks into the camera with heavy-lidded, sultry eyes",
    "solo": "She looks into the camera with heavy-lidded, sultry eyes",
    "feet": "She looks into the camera with a slow, teasing, heavy-lidded look",
    "oral": "She looks up with hungry, heavy-lidded eyes",
    "sex": "Her eyes are half-closed and her lips parted in a moan of pleasure",
    "climax": "She looks up with dazed, heavy-lidded, satisfied eyes",
    "outro": "She looks into the camera with tired, satisfied, heavy-lidded eyes",
}
STOP = set("with that this from they them their into over under after before about while where when what "
           "have their there then than your just very also only some more most".split())


def keywords(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", (text or "").lower()) if w not in STOP}


def similarity(a: str, b: str) -> float:
    ka, kb = keywords(a), keywords(b)
    return len(ka & kb) / len(ka | kb) if ka and kb else 0.0


def brief(plan: Plan, lib: Library, avoid_titles: list[dict]) -> dict[str, Any]:
    t = plan.theme
    pos = lib.positions
    return {
        "theme": {"title": t["title"], "hook": t["hook"], "notes": t.get("notes", ""), "mode": plan.reference_mode,
                  "shot 1 scene": t.get("shot1", ""), "first story pages": [o.get("scene", "") for o in t.get("opening", [])]},
        "her_role": lib.roles_her.get(t.get("her", ""), {}).get("label", t.get("her", "")),
        "his_role": lib.roles_him.get(t.get("him", ""), {}).get("label", t.get("him", "")) if t.get("cast") != "ff" else "",
        "location": plan.location["phrase"],
        "her_outfit": plan.her_outfit["phrase"],
        "his_outfit": plan.his_outfit["phrase"] if t.get("cast") != "ff" else "",
        "her_look": f"{plan.character.age}-year-old {plan.character.ethnicity} woman, {plan.character.hair}",
        "pages": [
            {
                "shot": p.shot, "slot": p.slot, "her_clothing_stage": p.her_stage, "man_on_page": p.him_stage != "absent",
                "position_id": p.position_id, "position": pos[p.position_id].get("her", ""),
                "alternatives": [{"id": a, "position": pos[a].get("her", "")} for a in p.alternatives],
            }
            for p in plan.pages
        ],
        "avoid_titles": avoid_titles,
    }


def default_outline(plan: Plan) -> dict:
    return {
        "title": plan.theme["title"],
        "logline": plan.theme["hook"],
        "pages": [{"shot": p.shot, "position_id": p.position_id, "beat": "", "emotion": DEFAULT_EMOTION[p.slot], "detail": ""}
                  for p in plan.pages],
        "source": "default",
    }


def check(out: Any, plan: Plan, v: Validator, lib: Library) -> list[str]:
    if not isinstance(out, dict) or not isinstance(out.get("pages"), list):
        return ["reply must be an object with a 'pages' list"]
    problems = []
    by_shot = {int(x.get("shot", -1)): x for x in out["pages"] if isinstance(x, dict)}
    for p in plan.pages:
        x = by_shot.get(p.shot)
        if not x:
            problems.append(f"shot {p.shot} missing")
            continue
        if x.get("position_id") not in [p.position_id, *p.alternatives]:
            problems.append(f"shot {p.shot}: position_id must be one of {[p.position_id, *p.alternatives]}")
        text = " ".join(str(x.get(k, "")) for k in ("beat", "emotion", "detail"))
        problems += [f"shot {p.shot}: {i}" for i in v.text_issues(text)]
        problems += [f"shot {p.shot}: {i}" for i in emotion_issues(lib, p.slot, str(x.get("emotion", "")))]
    problems += [f"title/logline: {i}" for i in v.text_issues(f"{out.get('title', '')} {out.get('logline', '')}")]
    return problems


def make_outline(llm, plan: Plan, lib: Library, cfg: Config, v: Validator, recent: list[dict]) -> dict:
    system = (Path(cfg.path(cfg.data_dir)) / "prompting" / "outline_system.md").read_text()
    b = brief(plan, lib, recent)
    note: Optional[str] = None
    for attempt in range(3):
        if note:
            b["fix_this"] = note
        try:
            out = llm.json(system, json.dumps(b, ensure_ascii=False), cfg.llm.outline, "outline")
        except Exception as e:  # refusal, no JSON, network: the album is still made from the theme
            d = default_outline(plan)
            d["source"] = f"default (LLM error: {str(e)[:120]})"
            return d
        problems = check(out, plan, v, lib)
        if problems:
            note = "Your previous reply had these problems, fix them: " + "; ".join(problems[:12])
            continue
        too_close = [r for r in recent if similarity(out.get("logline", ""), r["logline"]) >= cfg.memory.similarity_threshold]
        if too_close and attempt == 0:
            note = f"The story is too close to an earlier album ('{too_close[0]['title']}'). Write a clearly different one."
            continue
        by_shot = {int(x["shot"]): x for x in out["pages"]}
        for p in plan.pages:  # apply allowed position swaps, never one that repeats a pose already in the album
            new = by_shot[p.shot]["position_id"]
            if new != p.position_id and new not in {q.position_id for q in plan.pages}:
                p.position_id = new
            by_shot[p.shot]["position_id"] = p.position_id
        out["source"] = "llm"
        return out
    d = default_outline(plan)
    d["source"] = "default (LLM reply unusable)"
    return d
