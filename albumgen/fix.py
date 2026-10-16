"""Fix pages of an album that is already rendered: rebuild the chosen pages with the current composer (recipe pose
and pool emotion, no LLM), swap poses that fail for proven ones, then re-render only those pages.

Rules for a rebuilt page:
- a pose marked avoid is replaced (its replace_with, else the first proven pose of the slot that fits);
- penetration, oral, the finish and the last pages are naked (outfit_again does not exist any more);
- an album has one finish: a climax page followed by another climax page becomes one more position;
- a pose that is already in the album takes another camera angle."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Callable, Optional

from .compose import assemble, fallback_fields
from .library import Library, has_man
from .sampler import STAGE_LEVEL, Character, Man, Page, Plan, needs_met

PROVEN = {
    "intro": ["seated_flirt_clothed", "both_seated_sofa", "kiss_clothed_couple"],
    "tease": ["tease_pov_from_chair", "solo_kneel_hands_behind_head", "tease_breasts_kneeling", "tease_bend_over_look_back",
              "neck_kiss_from_behind", "kiss_clothed_couple"],
    "solo": ["solo_kneel_hands_behind_head", "solo_seated_side_legs", "solo_lying_top_down", "solo_all_fours_look_back"],
    "oral": ["oral_kneeling_profile", "oral_pov_kneeling_steep", "oral_lying_stomach_bed_edge", "oral_sitting_bed_edge_3q",
             "cunnilingus", "handjob"],
    "feet": ["feet_soles_closeup", "feet_massage", "feet_stockings_tease"],
    "sex": ["cowgirl_pov_below", "missionary_pov", "doggy_pov_kneeling", "reverse_cowgirl", "bed_edge_missionary_pov",
            "cowgirl_lean_forward_pov", "from_behind_standing_pov", "chair_riding_pov", "feet_on_chest_pov"],
    "climax": ["cumshot_breasts_kneeling", "facial_closeup", "cum_on_back", "cum_on_stomach_lying"],
    "outro": ["outro_side_curled", "afterglow_top_down", "outro_stomach_spent", "outro_sprawled_breathless",
              "outro_under_sheet", "outro_edge_messy"],
}
FF_PROVEN = {
    "intro": ["ff_lingerie_kneel"], "tease": ["ff_kiss_standing", "ff_kiss_lying", "ff_undress_each_other"],
    "oral": ["ff_cunnilingus_edge", "ff_cunnilingus", "ff_cunnilingus_swap", "ff_breast_kiss"],
    "sex": ["ff_fingering", "ff_spoon_fingering", "ff_facesit", "ff_cunnilingus_edge", "ff_kiss_lying"],
    "climax": ["ff_fingering"],
    "outro": ["ff_afterglow", "ff_afterglow_cuddle"],
}
NAKED_SLOTS = ("sex", "climax", "outro")
HIS = {"clothed": 0, "shirtless": 1, "nude": 2}
LEVEL_STAGE = {v: k for k, v in STAGE_LEVEL.items()}


def load_plan(album_dir: Path) -> Plan:
    data = json.loads((album_dir / "plan.json").read_text())
    p = data.get("plan", data)
    c = {k: v for k, v in p["character"].items() if k in Character.__dataclass_fields__}
    m = {k: v for k, v in p["man"].items() if k in Man.__dataclass_fields__}
    partner = p.get("partner")
    pages = [Page(**{k: v for k, v in pg.items() if k in Page.__dataclass_fields__}) for pg in p["pages"]]
    return Plan(album_id=p["album_id"], seed=p.get("seed", 0), theme=p["theme"], arc_id=p["arc_id"], location=p["location"],
                her_outfit=p["her_outfit"], his_outfit=p["his_outfit"], reference_mode=p.get("reference_mode", "solo"),
                character=Character(**c), man=Man(**m), pages=pages,
                partner=Character(**{k: v for k, v in partner.items() if k in Character.__dataclass_fields__}) if partner else None,
                footwear=p.get("footwear", ""), partner_outfit=p.get("partner_outfit"))


def _fits(plan: Plan, lib: Library, pid: str, stage: Optional[str] = None) -> bool:
    """A pose a rebuilt page may use: proven (no weak or avoid: the page is rebuilt because something failed)."""
    pos = lib.positions.get(pid)
    if not pos or pos.get("status") in ("avoid", "weak") or pos.get("theme_only") or pos.get("only_with_kink"):
        return False
    if pos.get("needs_his") and not re.search(rf"(?<![\w-])(?:{pos['needs_his']})", plan.his_outfit.get("phrase", "")):
        return False
    cast = "ff" if plan.reference_mode == "ff" else "mf"
    if pos.get("cast", "mf") != cast:
        return False
    if pos.get("needs_his_face") and plan.reference_mode != "couple":
        return False
    if pos.get("modes") and plan.reference_mode not in pos["modes"]:
        return False
    if pos.get("needs") and not needs_met(pos["needs"], plan.location):
        return False
    if stage and pos.get("stages") and not pos.get("penetration") and stage not in pos["stages"]:
        return False
    return True


def choose(plan: Plan, lib: Library, slot: str, current: str, used: set[str], stage: str) -> str:
    """The pose for a rebuilt page: the current one if it still works at this clothing stage, else a proven one not
    yet in the album."""
    cur = lib.positions.get(current, {})
    if cur.get("status") not in (None, "avoid", "weak") and cur.get("slot") == slot and not cur.get("theme_only"):
        if not cur.get("stages") or cur.get("penetration") or stage in cur["stages"] or slot in NAKED_SLOTS:
            return current  # the page failed on the face or the clothes, the pose itself rendered: keep it
    rw = lib.positions.get(current, {}).get("replace_with")
    if rw and _fits(plan, lib, rw, stage) and rw not in used:
        return rw
    pool = (FF_PROVEN if plan.reference_mode == "ff" else PROVEN).get(slot, PROVEN["sex"])
    if plan.reference_mode == "couple" and slot in ("intro", "tease"):  # he stays in the story
        pool = sorted(pool, key=lambda p: not has_man(lib.positions.get(p, {})))
    fresh = [p for p in pool if _fits(plan, lib, p, stage) and p not in used]
    if fresh:
        return fresh[0]
    ok = [p for p in pool if _fits(plan, lib, p, stage)]
    if ok:  # every proven pose is already in the album: the least repeated one, another camera
        counts = {p: sum(1 for q in plan.pages if q.position_id == p) for p in ok}
        return min(ok, key=lambda p: (counts[p], ok.index(p)))
    # nothing in this slot fits: a pose of a neighbouring slot (never a sex pose on an intro page)
    fall = {"intro": ["tease", "solo"], "tease": ["solo", "intro"], "solo": ["tease"]}.get(slot, ["sex"])
    pool = [p for f in fall for p in (FF_PROVEN if plan.reference_mode == "ff" else PROVEN).get(f, [])]
    return ([p for p in pool if _fits(plan, lib, p, stage) and p not in used] or [current])[0]


def rebuild(plan: Plan, lib: Library, shots: dict[int, Optional[str]]) -> dict[int, str]:
    """Changes plan.pages in place for the given shots ({shot: forced pose id or None}) and for every later page that
    would otherwise break the album's rules (clothes coming back); returns {shot: prompt}."""
    by_shot = {p.shot: p for p in plan.pages}
    climaxes = [p.shot for p in plan.pages if p.slot == "climax"]
    for s in climaxes[:-1]:  # one finish per album: an earlier climax page becomes one more position
        shots.setdefault(s, None)
        by_shot[s].slot = "sex"
    her_max, his_max = -1, -1
    for page in plan.pages:
        s = page.shot
        if page.her_stage == "outfit_again":
            shots.setdefault(s, None)
        her_lv = STAGE_LEVEL.get(page.her_stage, 4)
        his_lv = HIS.get(page.him_stage, -1)
        if s not in shots and (her_lv < her_max or (his_lv >= 0 and his_lv < his_max)):
            shots[s] = None  # clothes would come back after an earlier rebuilt page
        if s in shots:
            if page.her_stage == "outfit_again" or page.slot == "outro":
                page.slot = "outro"
            stage = LEVEL_STAGE[max(min(her_lv, 4), her_max, 0)]
            used = {p.position_id for p in plan.pages if p.shot != s}
            pid = shots[s] or choose(plan, lib, page.slot, page.position_id, used, stage)
            pos = lib.positions[pid]
            page.position_id = pid
            if pos.get("penetration") or page.slot in NAKED_SLOTS:
                stage = "nude"
            page.her_stage = stage
            if plan.reference_mode == "ff" or not has_man(pos):
                page.him_stage = "absent"
            else:
                want = pos.get("his", "any")
                lv = max(HIS.get(page.him_stage, 0), his_max, HIS.get(want, 0) if want != "any" else 0)
                if pos.get("penetration") or page.slot in ("oral", "climax"):
                    lv = 2
                page.him_stage = {0: "clothed", 1: "shirtless", 2: "nude"}[lv]
            page.take = sum(1 for p in plan.pages if p.shot < s and p.position_id == pid)
        her_max = max(her_max, STAGE_LEVEL.get(page.her_stage, 4))
        if page.him_stage in HIS:
            his_max = max(his_max, HIS[page.him_stage])
    return {s: assemble(plan, lib, by_shot[s], fallback_fields(plan, lib, by_shot[s])) for s in sorted(shots)}


def prepare(album_dir: Path, lib: Library, shots: dict[int, Optional[str]], log: Callable[[str], None] = print,
            memory=None) -> dict[int, str]:
    """Rewrites album.json, plan.json and story.md for the given pages (and any later page that would break the
    album's rules), updates the album in memory and marks the pages for a re-render (old images go to _replaced/)."""
    plan = load_plan(album_dir)
    prompts = rebuild(plan, lib, dict(shots))
    requests = json.loads((album_dir / "album.json").read_text())
    for r in requests:
        if int(r["shot"]) in prompts:
            r["prompt"] = prompts[int(r["shot"])]
    (album_dir / "album.json").write_text(json.dumps(requests, indent=2, ensure_ascii=False))
    pj = json.loads((album_dir / "plan.json").read_text())
    target = pj["plan"] if "plan" in pj else pj
    target["pages"] = [{**pg, **{k: getattr(p, k) for k in ("slot", "her_stage", "him_stage", "position_id", "take")}}
                       for pg, p in zip(target["pages"], plan.pages)]
    (album_dir / "plan.json").write_text(json.dumps(pj, indent=2, ensure_ascii=False, default=str))
    rj = album_dir / "render.json"
    results = json.loads(rj.read_text()) if rj.exists() else []
    keep = album_dir / "_replaced"
    keep.mkdir(exist_ok=True)
    for r in results:
        s = int(r["shot"])
        if s in prompts:
            img = album_dir / "images" / f"{s:02d}.jpg"
            if img.exists():
                n = len(list(keep.glob(f"{s:02d}-*.jpg")))
                shutil.move(str(img), str(keep / f"{s:02d}-{n + 1}.jpg"))
            r["status"], r["error"] = "failed", {"code": "review", "message": "rebuilt after review"}
    rj.write_text(json.dumps(results, indent=2))
    from .pipeline import story_md  # here: pipeline imports compose, which this module also uses

    sources = {int(k): v for k, v in (pj.get("sources") or {}).items()}
    sources.update({s: "rebuilt after review" for s in prompts})
    pj["sources"] = {str(k): v for k, v in sources.items()}
    (album_dir / "plan.json").write_text(json.dumps(pj, indent=2, ensure_ascii=False, default=str))
    (album_dir / "story.md").write_text(story_md(plan, lib, pj.get("outline", {}), requests, sources))
    if memory is not None:
        memory.set_positions(plan.album_id, [p.position_id for p in plan.pages])
    for s in sorted(prompts):
        log(f"shot {s}: {plan.pages[s - 2].position_id} ({plan.pages[s - 2].slot}/{plan.pages[s - 2].her_stage})")
    return prompts
