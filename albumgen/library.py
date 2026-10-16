"""Loads the YAML library (themes, roles, looks, places, outfits, kinks, positions, arcs, policy)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

STATUS_WEIGHT = {"strong": 1.0, "ok": 0.6, "weak": 0.15, "avoid": 0.0}
SLOTS = ("intro", "tease", "solo", "feet", "oral", "sex", "climax", "outro")


def _flat(groups: dict[str, list[dict]], key: str = "group") -> list[dict]:
    out = []
    for name, items in groups.items():
        for item in items or []:
            out.append({**item, key: name})
    return out


@dataclass
class Library:
    themes: list[dict]
    roles_her: dict[str, dict]
    roles_him: dict[str, dict]
    appearance: dict[str, Any]
    locations: dict[str, dict]
    outfits_her: dict[str, dict]
    outfits_his: dict[str, dict]
    footwear: dict[str, dict]
    accessories: dict[str, dict]
    kinks: dict[str, dict]
    positions: dict[str, dict]
    arcs: dict[str, dict]
    policy: dict[str, Any]
    emotions: dict[str, Any] = field(default_factory=dict)
    themes_by_id: dict[str, dict] = field(default_factory=dict)

    @classmethod
    def load(cls, data_dir: str | Path) -> "Library":
        d = Path(data_dir)
        y = lambda name: yaml.safe_load((d / name).read_text())  # noqa: E731
        themes = _flat(y("themes.yaml"), "family")
        roles = y("roles.yaml")
        outfits = y("outfits.yaml")
        kinks = y("kinks.yaml")
        lib = cls(
            themes=themes,
            roles_her={r["id"]: r for r in roles["her"]},
            roles_him={r["id"]: r for r in roles["him"]},
            appearance=y("appearance.yaml"),
            locations={x["id"]: x for x in _flat(y("locations.yaml"))},
            outfits_her={x["id"]: x for x in _flat(outfits["her"])},
            outfits_his={x["id"]: x for x in outfits["his"]},
            footwear={x["id"]: x for x in outfits.get("footwear", [])},
            accessories={x["id"]: x for x in outfits.get("accessories", [])},
            kinks={x["id"]: x for x in kinks["genres"] + kinks["body_and_look"] + kinks["fetish"]},
            positions={x["id"]: x for x in _flat(y("positions.yaml"), "slot")},
            arcs={a["id"]: a for a in y("arcs.yaml")},
            policy=y("policy.yaml"),
            emotions=y("emotions.yaml") if (d / "emotions.yaml").exists() else {},
        )
        lib.themes_by_id = {t["id"]: t for t in themes}
        for t in themes:  # a theme's opening story pages become positions only that theme can use
            for k, b in enumerate(t.get("opening") or []):
                pid = f"{t['id']}__open{k}"
                lib.positions[pid] = {"id": pid, "slot": "intro", "status": "ok", "beat": True, "theme_only": t["id"],
                                      "cast": t.get("cast", "mf"), "cam": b.get("cam", "pair"), "stage": b.get("stage", "outfit"),
                                      "his": b.get("his", "clothed"), "scene": b.get("scene", ""),
                                      "man": "none" if b.get("his") == "absent" or t.get("cast") == "ff" else "scene"}
        return lib

    def check(self) -> list[str]:
        """Reference integrity. Empty list = OK."""
        errs: list[str] = []
        seen: set[str] = set()
        for t in self.themes:
            if t["id"] in seen:
                errs.append(f"duplicate theme {t['id']}")
            seen.add(t["id"])
            if t.get("mode") not in ("couple", "solo", "ff"):
                errs.append(f"{t['id']}: mode {t.get('mode')}")
            for k, table in (("locations", self.locations), ("her_outfits", self.outfits_her),
                             ("his_outfits", self.outfits_his), ("kinks", self.kinks), ("arcs", self.arcs)):
                for x in t.get(k, []):
                    if x not in table:
                        errs.append(f"{t['id']}: {k} {x}")
        for p in self.positions.values():
            if p.get("replace_with") and p["replace_with"] not in self.positions:
                errs.append(f"position {p['id']}: replace_with {p['replace_with']}")
            if p["slot"] not in SLOTS:
                errs.append(f"position {p['id']}: slot {p['slot']}")
        for t in self.themes:
            for a in t.get("arcs", []):
                if a in self.arcs and self.arcs[a].get("cast", "mf") != t.get("cast", "mf"):
                    errs.append(f"{t['id']}: arc {a} is for cast {self.arcs[a].get('cast', 'mf')}")
        for a in self.arcs.values():
            if len(a["pages"]) != 15:
                errs.append(f"arc {a['id']}: {len(a['pages'])} pages")
        return errs

    # ---- policy helpers ----
    def never_words(self) -> list[str]:
        words: list[str] = []
        for k, v in self.policy["never_words"].items():
            if k != "notes":
                words.extend(v)
        return words

    def never_regex(self) -> re.Pattern:
        alts = sorted({re.escape(w) for w in self.never_words()}, key=len, reverse=True)
        return re.compile(r"(?<![\w])(" + "|".join(alts) + r")(?![\w])", re.I)

    def swaps(self) -> dict[str, str]:
        return dict(self.policy.get("swaps", {}))


def emotion_issues(lib: "Library", slot: str, text: str) -> list[str]:
    """Words that must not describe her face on this kind of page (laughing anywhere, smiling during sex)."""
    e = lib.emotions or {}
    words = list(e.get("banned_everywhere", [])) + list((e.get("banned_in_slots") or {}).get(slot, []))
    hits = sorted({w for w in words if re.search(rf"\b{re.escape(w)}\b", text or "", re.I)})
    return [f"emotion on a {slot} page must show desire or pleasure; remove: {', '.join(hits)}"] if hits else []


def emotion_for(lib: "Library", slot: str, key: int, ff: bool = False) -> str:
    pools = (lib.emotions.get("ff_pools") if ff else None) or lib.emotions.get("pools") or {}
    pool = pools.get(slot) or pools.get("sex") or ["Her eyes are half-closed and her lips parted."]
    return pool[key % len(pool)]


def has_man(position: dict) -> bool:
    return str(position.get("man", "none")).strip().lower() not in ("none", "")
