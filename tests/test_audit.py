import random

from albumgen.audit import audit, page_issues
from albumgen.memory import Memory
from albumgen.sampler import Sampler
from albumgen.validate import Validator


def test_sampled_albums_have_no_contradictions(cfg, lib):
    counts, examples = audit(cfg, lib, n=60, seed=7)
    assert sum(counts.values()) == 0, examples


def test_audit_catches_a_bed_in_a_kitchen_and_a_smile_during_sex(cfg, lib):
    plan = Sampler(lib, Memory(":memory:"), cfg.album, cfg.memory, random.Random(1)).plan(seed=1, theme_id="plumber_leak")
    page = next(p for p in plan.pages if p.slot == "sex")
    text = "Camera: side view. She lies on the bed and smiles widely."
    issues = page_issues(plan, lib, page, text, Validator(lib), seen_climax=False)
    assert "bed word without a bed" in issues and "smile or laugh during sex" in issues
