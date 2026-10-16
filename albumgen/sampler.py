"""Picks the album skeleton without an LLM: theme, arc, place, outfits, her look (and her partner's in two-women
albums), his look, and one position per page. Weighted random choice x novelty from memory x model status.

Modes (from the theme): couple = shot 1 shows them meeting, his face is in the reference and may appear later;
solo = told through his eyes, his face never shows; ff = two women."""

from __future__ import annotations

import hashlib
import random
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Optional

from .config import AlbumConfig, MemoryConfig
from .library import STATUS_WEIGHT, Library, has_man
from .memory import Memory

HAIR_GROUPS = {"dark": ("black", "dark brown", "chestnut", "honey-brown"), "light": ("blonde",),
               "red": ("auburn", "copper", "strawberry", "burgundy"), "grey": ("silver", "grey"), "pink": ("pink",)}


def hair_group(colour: str) -> str:
    for g, keys in HAIR_GROUPS.items():
        if any(k in colour for k in keys):
            return g
    return "dark"


@dataclass
class Character:
    age: int
    ethnicity: str
    skin: str
    hair: str  # full phrase, e.g. "jet-black hair in a sleek chin-length bob with straight bangs"
    eyes: str
    figure: str  # full phrase for shot 1
    figure_short: str  # identity sentence
    makeup: str  # full phrase for shot 1
    makeup_short: str
    extra: str = ""  # optional detail kept on every page ("thin black-framed glasses")
    fingerprint: str = ""
    hair_colour: str = ""

    @property
    def name(self) -> str:
        """How the prompts refer to her in two-women albums."""
        g = hair_group(self.hair_colour)
        return {"dark": "the dark-haired woman", "light": "the blonde woman", "red": "the red-haired woman",
                "grey": "the silver-haired woman", "pink": "the pink-haired woman"}[g]


@dataclass
class Man:
    age: int
    build: str
    skin: str
    nude_details: str
    hair_face: str  # his hair and face: used when shot 1 shows him (couple mode)

    @property
    def age_phrase(self) -> str:
        a = self.age
        if a < 30:
            return "late twenties"
        if a < 35:
            return "early thirties"
        if a < 40:
            return "late thirties"
        if a < 45:
            return "early forties"
        if a < 50:
            return "late forties"
        return "fifties"

    @property
    def sentence(self) -> str:
        return f"He is a separate adult man in his {self.age_phrase} with {self.build} and {self.skin} skin."

    @property
    def face_sentence(self) -> str:
        return f"He is a separate adult man in his {self.age_phrase} with {self.build}, {self.hair_face} and {self.skin} skin."


@dataclass
class Page:
    shot: int  # 2..16
    slot: str
    her_stage: str
    him_stage: str
    position_id: str
    alternatives: list[str] = field(default_factory=list)
    take: int = 0  # 1, 2 ... when the same pose repeats in the album: another camera angle


@dataclass
class Plan:
    album_id: str
    seed: int
    theme: dict
    arc_id: str
    location: dict
    her_outfit: dict
    his_outfit: dict
    reference_mode: str  # solo | couple | ff
    character: Character
    man: Man
    pages: list[Page]
    partner: Optional[Character] = None  # the second woman (ff)
    footwear: str = ""  # e.g. "black heels"; empty = barefoot
    partner_outfit: Optional[dict] = None  # two-women albums: her friend wears another outfit of the theme

    def to_dict(self) -> dict:
        d = asdict(self)
        d["man"] = {**asdict(self.man), "sentence": self.man.sentence}
        return d


def _pick(rng: random.Random, items: list, weights: list[float]):
    total = sum(weights)
    if not items or total <= 0:
        return None
    return rng.choices(items, weights=weights, k=1)[0]


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:24]


class Sampler:
    def __init__(self, lib: Library, memory: Memory, album: AlbumConfig, mem: MemoryConfig, rng: random.Random):
        self.lib, self.memory, self.cfg, self.mcfg, self.rng = lib, memory, album, mem, rng
        self.feedback = memory.position_stats()

    # ---------- weights ----------
    def _status_w(self, status: str) -> float:
        if status == "weak" and self.cfg.untested == "off":
            return 0.0
        return STATUS_WEIGHT.get(status, 0.6)

    def _theme_allowed(self, t: dict) -> bool:
        if t["id"] in self.cfg.exclude_themes:
            return False
        if self.cfg.only_families and t["family"] not in self.cfg.only_families:
            return False
        if t["family"] in self.cfg.exclude_families:
            return False
        if set(t.get("kinks", [])) & set(self.cfg.exclude_kinks):
            return False
        return self._status_w(t.get("status", "ok")) > 0

    # ---------- choices ----------
    def theme(self, theme_id: Optional[str]) -> dict:
        if theme_id:
            if theme_id not in self.lib.themes_by_id:
                raise KeyError(f"unknown theme {theme_id}")
            return self.lib.themes_by_id[theme_id]
        pool = [t for t in self.lib.themes if self._theme_allowed(t)]
        if not pool:
            raise ValueError("no theme left after the filters in config.album")
        used = self.memory.counts("theme_id")
        fams = self.memory.counts("family")
        recent = self.memory.recent_themes(self.mcfg.theme_window)
        floor = min(used.get(t["id"], 0) for t in pool)  # "deck of cards": least-used themes first
        weights = []
        for t in pool:
            w = self._status_w(t.get("status", "ok"))
            w /= 1 + fams.get(t["family"], 0) * 0.5  # spread albums over families
            if used.get(t["id"], 0) > floor:
                w *= 0.05
            if t["id"] in recent:
                w *= 0.01
            weights.append(w)
        return _pick(self.rng, pool, weights)

    def arc(self, theme: dict, arc_id: Optional[str]) -> str:
        if arc_id:
            if arc_id not in self.lib.arcs:
                raise KeyError(f"unknown arc {arc_id}")
            return arc_id
        cast = theme.get("cast", "mf")
        pool = [a for a in theme.get("arcs", []) if a in self.lib.arcs] or \
               [a for a, v in self.lib.arcs.items() if v.get("cast", "mf") == cast]
        used = self.memory.counts("arc_id")
        floor = min(used.get(a, 0) for a in pool)
        return _pick(self.rng, pool, [1.0 if used.get(a, 0) <= floor else 0.3 for a in pool])

    def place_and_outfit(self, theme: dict) -> tuple[dict, dict, dict]:
        recent = self.memory.recent_pairs(self.mcfg.pair_window)
        locs = [self.lib.locations[x] for x in theme["locations"]]
        outs = [self.lib.outfits_her[x] for x in theme["her_outfits"]]
        loc = out = None
        for _ in range(30):
            loc = _pick(self.rng, locs, [self._status_w(x.get("status", "ok")) or 0.05 for x in locs])
            out = _pick(self.rng, outs, [self._status_w(x.get("status", "ok")) or 0.05 for x in outs])
            if (loc["id"], out["id"]) not in recent:
                break
        his_ids = theme.get("his_outfits") or ["tshirt_jeans"]
        his = self.lib.outfits_his[self.rng.choice(his_ids)]
        return loc, out, his

    def character(self, theme: dict, look: dict | None = None, avoid_group: str | None = None) -> Character:
        ap = self.lib.appearance["her"]
        look = look or {}
        role = self.lib.roles_her.get(theme.get("her", ""), {})
        lo, hi = look.get("age") or theme.get("her_age") or role.get("age") or [self.cfg.min_age, self.cfg.max_age]
        lo = max(lo, self.cfg.min_age)
        if not look.get("age"):  # a theme's own look (e.g. mature 56-66) may go past the default max age
            hi = min(hi, self.cfg.max_age)
        if lo > hi:
            lo, hi = self.cfg.min_age, self.cfg.max_age
        w = lambda items: [x.get("weight", 1) for x in items]  # noqa: E731
        for _ in range(80):
            age = self.rng.randint(lo, hi)
            eth = _pick(self.rng, ap["ethnicity"], w(ap["ethnicity"]))
            skin = self.rng.choice(eth["skin"])
            colours = [c for c in ap["hair_colour"] if age >= c.get("min_age", 0)]
            if look.get("hair_colours"):
                colours = [{"colour": c, "weight": 1} for c in look["hair_colours"]]
            if avoid_group:
                colours = [c for c in colours if hair_group(c["colour"]) != avoid_group] or colours
            colour = _pick(self.rng, colours, w(colours))["colour"]
            cuts = [c for c in ap["hair_length_cut"] if not c.get("fits") or eth["id"] in c["fits"]]
            cut = _pick(self.rng, cuts, w(cuts))["cut"]
            hair = _hair_phrase(colour, cut)
            fig = _pick(self.rng, ap["figure"], w(ap["figure"]))
            if look.get("figure"):
                fig = {"phrase": look["figure"], "short": look.get("figure_short", look["figure"])}
            age = max(age, fig.get("min_age", 0))  # slim figures read younger: keep them clearly adult
            makeup = _pick(self.rng, ap["makeup"], w(ap["makeup"]))
            extra = look.get("extra", "")
            if not extra:
                extras = [x for x in ap.get("extras", []) if self._status_w(x.get("status", "ok")) > 0.2]
                if extras and self.rng.random() < 0.25:
                    extra = self.rng.choice(extras)["phrase"]
            fp = hashlib.sha1(f"{eth['id']}|{colour}|{cut}|{fig['phrase']}|{age // 5}".encode()).hexdigest()[:16]
            if not self.memory.has_fingerprint(fp):
                break
        return Character(age=age, ethnicity=eth["phrase"], skin=skin, hair=hair, eyes=self.rng.choice(ap["eyes"]),
                         figure=fig["phrase"], figure_short=fig.get("short") or re.sub(r"^an? ", "", fig["phrase"]),
                         makeup=makeup["phrase"], makeup_short=makeup.get("short") or makeup["phrase"],
                         extra=extra, fingerprint=fp, hair_colour=colour)

    def man(self, theme: dict) -> Man:
        ap = self.lib.appearance["him"]
        role = self.lib.roles_him.get(theme.get("him", ""), {})
        band = _pick(self.rng, ap["age_bands"], [b.get("weight", 1) for b in ap["age_bands"]])
        (blo, bhi), (rlo, rhi) = band["range"], theme.get("him_age") or role.get("age") or band["range"]
        lo, hi = max(blo, rlo, 23), min(bhi, rhi)
        if lo > hi:  # the theme's range and the band do not overlap: the theme wins
            lo, hi = max(23, rlo), max(23, rhi)
        return Man(age=self.rng.randint(lo, hi), build=self.rng.choice(ap["build"]), skin=self.rng.choice(ap["skin"]),
                   nude_details=self.rng.choice(ap["nude_details"]), hair_face=self.rng.choice(ap["hair_face_couple_mode"]))

    def story_slots(self, arc_id: str, mode: str) -> list[tuple[str, str, str]]:
        """The arc's pages with the story rules applied: one finish per album (the last climax page; earlier climax
        pages become one more position), and in couple albums he stays in the story (a solo page becomes a tease page)."""
        slots = [tuple(x) for x in self.lib.arcs[arc_id]["pages"]]
        climaxes = [i for i, s in enumerate(slots) if s[0] == "climax"]
        for i in climaxes[:-1]:
            slots[i] = ("sex", "nude", "nude")
        if mode == "couple":
            his = "clothed"
            for i, (slot, her, him) in enumerate(slots):
                if him != "absent":
                    his = him
                elif slot == "solo":
                    slots[i] = ("tease", her, his)
        return slots

    def pages(self, arc_id: str, theme: dict | None = None, location: dict | None = None,
              allow_face: bool = False, mode: str = "solo", his_outfit: dict | None = None) -> list[Page]:
        theme = theme or {}
        cast = theme.get("cast", "mf")
        focus = "feet" if "feet" in theme.get("kinks", []) else ""
        recent = self.memory.recent_positions(self.mcfg.position_window)
        ever = self.memory.position_counts()
        beats = [p for p in self.lib.positions.values() if p.get("theme_only") == theme.get("id")]
        beats.sort(key=lambda p: p["id"])
        chosen: list[str] = []
        weak_left = self.cfg.max_weak_per_album if self.cfg.untested == "light" else 0
        pages: list[Page] = []
        her_level, his_level = 0, -1  # clothing only comes off as the album goes on
        for i, (slot, arc_her, arc_him) in enumerate(self.story_slots(arc_id, mode)):
            # the theme's own story pages open the album
            if beats and slot in ("intro", "tease", "solo"):
                b = beats.pop(0)
                stage = b.get("stage", "outfit")
                her_level = max(her_level, STAGE_LEVEL.get(stage, 0))
                stage = LEVEL_STAGE[her_level]
                him = b.get("his", "clothed")
                if cast == "ff" or him == "absent":
                    him = "absent"
                else:
                    his_level = max(his_level, HIS_LEVEL.get(him, 0))
                    him = LEVEL_HIS[his_level]
                chosen.append(b["id"])
                pages.append(Page(shot=i + 2, slot="intro", her_stage=stage, him_stage=him, position_id=b["id"]))
                continue
            want_man = arc_him != "absent"
            stage = LEVEL_STAGE[max(STAGE_LEVEL.get(arc_her, 4), her_level)]

            def candidates(match_man: bool, match_stage: bool, slot_name: str = slot) -> list[tuple[dict, float]]:
                out = []
                for p in self.lib.positions.values():
                    if p["slot"] != slot_name or p["id"] in chosen or p.get("theme_only"):
                        continue
                    if p.get("cast", "mf") != cast:
                        continue
                    status = p.get("status", "ok")
                    if status == "weak" and (weak_left <= 0 or slot == "climax"):
                        continue
                    if p.get("needs_his_face") and not allow_face:
                        continue
                    if p.get("modes") and mode not in p["modes"]:
                        continue  # e.g. arriving at the door repeats the meeting of a couple album
                    if p.get("only_with_kink") and p["only_with_kink"] not in theme.get("kinks", []):
                        continue
                    if p.get("needs") and not needs_met(p["needs"], location):
                        continue
                    if p.get("needs_his") and not re.search(rf"(?<![\w-])(?:{p['needs_his']})", (his_outfit or {}).get("phrase", "")):
                        continue  # e.g. unbuttoning his shirt when he wears a t-shirt
                    if match_man and cast == "mf" and has_man(p) != want_man:
                        continue
                    if match_stage and p.get("stages") and stage not in p["stages"]:
                        continue
                    if p.get("his_strict") and HIS_LEVEL.get(p.get("his"), 0) < his_level:
                        continue  # e.g. undressing him after he is already naked
                    w = self._status_w(status)
                    good, bad = self.feedback.get(p["id"], (0, 0))
                    w *= max(0.1, (good + 2) / (good + bad + 2))  # learns from `albumgen feedback`
                    w /= (1 + recent.get(p["id"], 0)) ** 2  # strong novelty push: poses used recently are rarer
                    if not ever.get(p["id"]):
                        w *= 2.5  # a pose no album has shown yet
                    if focus == "feet" and re.search(r"\b(soles?|feet|foot|toes)\b", f"{p.get('camera', '')} {p.get('her', '')}"):
                        w *= 4
                    if allow_face and p.get("needs_his_face"):
                        w *= 1.5  # couple albums: show them together
                    if mode == "couple":
                        w *= p.get("couple_weight", 1.0)
                    if w > 0:
                        out.append((p, w))
                return out

            cands = candidates(True, True) or candidates(False, True)
            for alt_slot in NEIGHBOUR_SLOTS.get(slot, []):  # e.g. a tease page after she is naked becomes a solo page
                cands = cands or candidates(True, True, alt_slot) or candidates(False, True, alt_slot)
            cands = cands or candidates(True, False) or candidates(False, False)
            if not cands:  # every position of the slot already used: allow a repeat
                cands = [(p, self._status_w(p.get("status", "ok"))) for p in self.lib.positions.values()
                         if p["slot"] == slot and p.get("cast", "mf") == cast and p.get("status") not in ("weak", "avoid")
                         and not p.get("theme_only") and not p.get("only_with_kink")
                         and (not p.get("needs") or needs_met(p["needs"], location))
                         and (allow_face or not p.get("needs_his_face"))]
            pos = _pick(self.rng, [c[0] for c in cands], [c[1] for c in cands])
            if pos.get("status") == "weak":
                weak_left -= 1
            chosen.append(pos["id"])
            allowed = pos.get("stages") or []
            if pos.get("penetration"):
                stage = "nude"
            elif allowed and stage not in allowed:
                later = [s for s in allowed if STAGE_LEVEL.get(s, 9) >= her_level]
                if later:
                    stage = later[0]
            her_level = max(her_level, STAGE_LEVEL.get(stage, 4))
            if cast == "ff" or not has_man(pos):
                him = "absent"
            else:
                want = pos.get("his", "any")
                base = HIS_LEVEL.get(want if want != "any" else (arc_him if arc_him not in ("absent", "any") else "clothed"), 0)
                his_level = max(his_level, base)
                him = LEVEL_HIS[his_level]
            alts = [c[0]["id"] for c in sorted(cands, key=lambda c: -c[1])
                    if c[0]["id"] != pos["id"] and c[0].get("status") != "weak"
                    and bool(c[0].get("penetration")) == bool(pos.get("penetration"))
                    and has_man(c[0]) == has_man(pos)
                    and (pos.get("penetration") or not c[0].get("stages") or stage in c[0]["stages"])][:2]
            pages.append(Page(shot=i + 2, slot=slot, her_stage=stage, him_stage=him,
                              position_id=pos["id"], alternatives=alts, take=chosen.count(pos["id"]) - 1))
        return pages

    def plan(self, *, theme_id: Optional[str] = None, arc_id: Optional[str] = None,
             mode: Optional[str] = None, seed: int = 0) -> Plan:
        theme = self.theme(theme_id)
        arc = self.arc(theme, arc_id)
        loc, out, his = self.place_and_outfit(theme)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        album_id = f"{stamp}-{_slug(theme['id'])}-{self.rng.randrange(16**4):04x}"
        cast = theme.get("cast", "mf")
        ref_mode = "ff" if cast == "ff" else (mode or theme.get("mode") or self.cfg.reference_mode)
        her = self.character(theme, theme.get("look"))
        partner = self.character(theme, theme.get("look2"), avoid_group=hair_group(her.hair_colour)) if cast == "ff" else None
        allow_face = ref_mode == "couple" or self.cfg.allow_his_face
        partner_outfit = None
        if partner is not None:
            others = [self.lib.outfits_her[x] for x in theme["her_outfits"] if x != out["id"]]
            partner_outfit = self.rng.choice(others) if others else out
        return Plan(album_id=album_id, seed=seed, theme=theme, arc_id=arc, location=loc, her_outfit=out,
                    his_outfit=his, reference_mode=ref_mode, character=her, man=self.man(theme),
                    pages=self.pages(arc, theme, loc, allow_face, ref_mode, his), partner=partner, footwear=theme.get("footwear", ""),
                    partner_outfit=partner_outfit)


def _hair_phrase(colour: str, cut: str) -> str:
    """'jet-black' + 'a sleek chin-length bob with straight bangs' -> 'jet-black hair in a sleek chin-length bob ...'"""
    if cut.startswith(("a ", "an ")):
        return f"{colour} hair in {cut}"
    if " hair" in cut:
        return cut.replace(" hair", f" {colour} hair", 1)
    return f"{colour} hair in {cut}"


def needs_met(needs: str, location: dict | None) -> bool:
    """`needs: "bed|sofa"` is met when any alternative appears as a word in the location phrase or props."""
    text = f"{(location or {}).get('phrase', '')} {(location or {}).get('props', '')}".lower()
    return any(re.search(rf"\b{re.escape(alt.strip())}s?\b", text) for alt in needs.split("|"))


STAGE_LEVEL = {"outfit": 0, "partial": 1, "underwear": 2, "topless": 3, "nude": 4}
LEVEL_STAGE = {v: k for k, v in STAGE_LEVEL.items()}
NEIGHBOUR_SLOTS = {"tease": ["solo"], "intro": ["tease", "solo"], "solo": ["tease"], "feet": ["solo"]}
HIS_LEVEL = {"clothed": 0, "shirtless": 1, "nude": 2}
LEVEL_HIS = {v: k for k, v in HIS_LEVEL.items()}
