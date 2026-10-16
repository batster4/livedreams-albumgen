import random

from albumgen.library import has_man
from albumgen.sampler import Sampler, needs_met


def _plan(lib, mem, cfg, seed, **kw):
    return Sampler(lib, mem, cfg.album, cfg.memory, random.Random(seed)).plan(seed=seed, **kw)


def test_pages_respect_status_rules(lib, mem, cfg):
    for seed in range(40):
        plan = _plan(lib, mem, cfg, seed)
        ids = [p.position_id for p in plan.pages]
        assert len(ids) == 15
        statuses = [lib.positions[i]["status"] for i in ids]
        assert "avoid" not in statuses
        assert statuses.count("weak") <= cfg.album.max_weak_per_album
        for p in plan.pages:
            pos = lib.positions[p.position_id]
            if p.slot == "climax":
                assert pos["status"] != "weak"
            if plan.reference_mode != "couple":
                assert not pos.get("needs_his_face")
            if pos.get("only_with_kink"):
                assert pos["only_with_kink"] in plan.theme["kinks"]
            if pos.get("needs"):
                assert needs_met(pos["needs"], plan.location)


def test_untested_off_means_no_weak(lib, mem, cfg):
    cfg.album.untested = "off"
    for seed in range(15):
        plan = _plan(lib, mem, cfg, seed)
        assert all(lib.positions[p.position_id]["status"] != "weak" for p in plan.pages)


def test_man_matches_arc_when_possible(lib, mem, cfg):
    plan = _plan(lib, mem, cfg, 3, arc_id="classic")
    for p in plan.pages:
        if p.him_stage == "absent":
            assert not has_man(lib.positions[p.position_id])


def test_age_range(lib, mem, cfg):
    for seed in range(30):
        plan = _plan(lib, mem, cfg, seed)
        lo, hi = (plan.theme.get("look") or {}).get("age") or (cfg.album.min_age, cfg.album.max_age)
        assert max(cfg.album.min_age, lo) <= plan.character.age <= max(cfg.album.max_age, hi)


def test_filters(lib, mem, cfg):
    cfg.album.only_families = ["workplace"]
    for seed in range(10):
        assert _plan(lib, mem, cfg, seed).theme["family"] == "workplace"
