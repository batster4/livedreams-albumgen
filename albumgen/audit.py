"""Contradiction audit: samples many albums (no LLM, recipe text) and checks every prompt against the rules that
reviews of rendered albums taught us. `albumgen audit -n 300` prints what breaks; tests run a small sample."""

from __future__ import annotations

import random
import re
from collections import Counter

from .compose import _side, assemble, fallback_fields, has_bed, man_part, shot1_prompt
from .config import Config
from .library import Library
from .memory import Memory
from .sampler import STAGE_LEVEL, Sampler
from .validate import Validator

BED_WORDS = re.compile(r"\b(bed|pillows?|mattress|sheets?|headboard)\b", re.I)
WORN = re.compile(r"\b(She wears|she still wears|She is in only|wearing only)\b")
SMILE = re.compile(r"\b(smil\w*|grin\w*|laugh\w*|giggl\w*)\b", re.I)
HIS_FACE = re.compile(r"\b(his face (?:visible|in profile|clearly)|both faces)\b", re.I)
MALE = re.compile(r"\b(he|him|his|man|penis|semen)\b", re.I)
SEMEN = re.compile(r"\bsemen\b", re.I)


def page_issues(plan, lib: Library, page, text: str, v: Validator, seen_climax: bool) -> list[str]:
    pos = lib.positions[page.position_id]
    out = []
    if not has_bed(plan.location) and BED_WORDS.search(text):
        out.append("bed word without a bed")
    if re.search(r"\bfloor\b", text) and re.search(r"\b(street|beach|garden|park|forest|yard|lawn)\b",
                                                    plan.location["phrase"].lower()):
        out.append("floor outdoors")
    man = man_part(plan, page, pos)
    if man and "She is alone in this shot" in text:
        out.append("alone and the man described")
    if page.her_stage == "nude" and plan.reference_mode != "ff" and WORN.search(text):
        out.append("naked and wearing")
    for sent in re.split(r"(?<=\.)\s", text):
        worn_part = re.sub(r"\b(her|the) [^;:]*?(lie|lies) on the (floor|ground|sand)[^;]*", "", sent)
        if "barefoot" in sent and re.search(r"\b(heels|stockings|boots|socks)\b", worn_part) and "off" not in worn_part:
            out.append("barefoot and footwear in one sentence")
    if page.slot in ("oral", "sex", "climax") and SMILE.search(text):
        out.append("smile or laugh during sex")
    elif SMILE.search(re.sub(r"half-smile", "", text)) and re.search(r"\b(laugh|grin|giggl)", text, re.I):
        out.append("laughing")
    if plan.reference_mode == "solo" and HIS_FACE.search(text):
        out.append("his face in a solo album")
    if plan.reference_mode == "ff" and MALE.search(text):
        out.append("a man in a two-women album")
    if SEMEN.search(text) and not seen_climax and page.slot != "climax":
        out.append("semen before the finish")
    if page.slot == "outro" and page.her_stage != "nude":
        out.append("dressed at the end")
    if pos.get("penetration") and "fully bare" not in text and plan.reference_mode != "ff":
        out.append("penetration without the naked sentence")
    if "{" in text or "}" in text:
        out.append("unfilled placeholder")
    if text.count("Camera:") != 1:
        out.append("camera sentence count")
    if pos.get("status") == "avoid":
        out.append(f"avoid pose {page.position_id}")
    m = re.search(r"White semen from earlier still glistens on her (.+?)\.", text)
    if m and pos.get("shows") in ("front", "face") and _side(m.group(1)) == "back":
        out.append("semen named where the camera cannot see it")
    out += [f"validator: {i}" for i in v.prompt_issues(text, page.shot)]
    return out


def audit(cfg: Config, lib: Library, n: int = 300, seed: int = 0) -> tuple[Counter, list[str]]:
    v = Validator(lib, cfg.album.min_age)
    counts: Counter = Counter()
    examples: list[str] = []
    for i in range(n):
        rng = random.Random(seed + i)
        plan = Sampler(lib, Memory(":memory:"), cfg.album, cfg.memory, rng).plan(seed=seed + i)
        problems = [f"shot 1: {x}" for x in v.prompt_issues(shot1_prompt(plan), 1)]
        level, ids, seen_climax = -1, Counter(), False
        for page in plan.pages:
            text = assemble(plan, lib, page, fallback_fields(plan, lib, page))
            problems += [f"shot {page.shot} {page.position_id}: {x}" for x in page_issues(plan, lib, page, text, v, seen_climax)]
            seen_climax = seen_climax or page.slot == "climax"
            lv = STAGE_LEVEL.get(page.her_stage, 4)
            if lv < level:
                problems.append(f"shot {page.shot}: clothing comes back")
            level = max(level, lv)
            ids[page.position_id] += 1
            if ids[page.position_id] > 1 and not page.take:
                problems.append(f"shot {page.shot}: repeated pose without a new camera")
        for p in problems:
            key = re.sub(r"^shot \d+ ?\S*: ", "", p)
            counts[key] += 1
            if len(examples) < 40:
                examples.append(f"{plan.theme['id']} ({plan.reference_mode}) {p}")
    return counts, examples
