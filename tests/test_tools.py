import json
from pathlib import Path

from PIL import Image

from albumgen.config import RenderConfig
from albumgen.export import export
from albumgen.fix import load_plan, prepare
from albumgen.llm import FakeLLM
from albumgen.memory import Memory
from albumgen.pipeline import make_album
from albumgen.render import Renderer
from albumgen.sampler import STAGE_LEVEL


def _album(cfg, lib, mem, theme="pizza_delivery", seed=3, images=True) -> Path:
    res = make_album(cfg, theme=theme, seed=seed, dry_run=True, library=lib, memory=mem)
    if images:
        (res.dir / "images").mkdir()
        for r in res.requests:
            Image.new("RGB", (64, 96), (40 * (r["shot"] % 6), 80, 120)).save(res.dir / "images" / f"{r['shot']:02d}.jpg")
        (res.dir / "render.json").write_text(json.dumps(
            [{"shot": r["shot"], "id": f"job_{r['shot']}", "status": "succeeded", "attempt": 1} for r in res.requests]))
    return res.dir


def test_fix_rebuilds_pages_keeps_rules_and_updates_memory(cfg, lib):
    mem = Memory(cfg.memory.db_path)
    d = _album(cfg, lib, mem)
    before = {p.shot: p.position_id for p in load_plan(d).pages}
    sex = next(p.shot for p in load_plan(d).pages if p.slot == "sex")
    prompts = prepare(d, lib, {sex: None, sex + 1: "reverse_cowgirl"}, log=lambda s: None, memory=mem)
    plan = load_plan(d)
    assert plan.pages[sex - 2].position_id == before[sex]  # only the face or the clothes failed: same pose
    assert plan.pages[sex - 1].position_id == "reverse_cowgirl"
    assert {sex, sex + 1} <= set(prompts)
    level = -1
    for p in plan.pages:  # clothes never come back
        assert STAGE_LEVEL.get(p.her_stage, 4) >= level
        level = STAGE_LEVEL.get(p.her_stage, 4)
    rj = {r["shot"]: r for r in json.loads((d / "render.json").read_text())}
    assert rj[sex]["status"] == "failed" and not (d / "images" / f"{sex:02d}.jpg").exists()
    assert (d / "_replaced" / f"{sex:02d}-1.jpg").exists()
    assert "rebuilt after review" in (d / "story.md").read_text()
    assert json.loads(mem.get(d.name)["positions"])[sex - 1] == "reverse_cowgirl"


def test_fix_replaces_retired_poses(cfg, lib):
    mem = Memory(cfg.memory.db_path)
    d = _album(cfg, lib, mem, theme="ff_roommates")
    pj = json.loads((d / "plan.json").read_text())
    page = next(p for p in pj["plan"]["pages"] if p["slot"] == "sex")
    page["position_id"] = "ff_69"  # retired since 2026-10-15
    (d / "plan.json").write_text(json.dumps(pj))
    prepare(d, lib, {page["shot"]: None}, log=lambda s: None)
    new = load_plan(d).pages[page["shot"] - 2].position_id
    assert new != "ff_69" and lib.positions[new]["status"] in ("ok", "strong")


def test_render_resumes_and_retries_once(tmp_path):
    calls = []

    class R(Renderer):
        def __init__(self):
            self.cfg, self.log = RenderConfig(), (lambda s: None)

        def _one(self, album_id, req, shot1_id, out, attempt=1):
            calls.append((req["shot"], attempt))
            if req["shot"] == 3 and attempt == 1:
                return {"shot": 3, "id": "j3", "status": "failed", "error": {"code": "job_timeout"}}
            if req["shot"] == 4:
                return {"shot": 4, "id": "j4", "status": "failed", "error": {"code": "content_rejected"}}
            (out / f"{req['shot']:02d}.jpg").write_bytes(b"x")
            return {"shot": req["shot"], "id": f"j{req['shot']}", "status": "succeeded"}

    (tmp_path / "album.json").write_text(json.dumps([{"shot": i, "model": "m", "prompt": "p", "params": {}} for i in range(1, 6)]))
    res = R().render(tmp_path)
    assert [r["status"] for r in res] == ["succeeded", "succeeded", "succeeded", "failed", "succeeded"]
    assert (3, 2) in calls and not any(c == (4, 2) for c in calls)  # timeouts get a new key, rejections do not
    calls.clear()
    R().render(tmp_path)  # second run: finished pages are kept
    assert all(shot in (4,) for shot, _ in calls if shot != 1) and (1, 1) not in calls


def test_export_writes_collages_index_and_zip(cfg, lib, tmp_path):
    mem = Memory(cfg.memory.db_path)
    a = _album(cfg, lib, mem, seed=1)
    b = _album(cfg, lib, mem, theme="boudoir_shoot", seed=2, images=False)  # not rendered: skipped
    out = tmp_path / "export"
    rows = export([a, b], out, log=lambda s: None)
    assert len(rows) == 1
    folder = out / rows[0]["slug"]
    assert len(list((folder / "images").glob("*.jpg"))) == 16
    with Image.open(folder / "collage.jpg") as im:
        assert im.size == (4 * 360, 4 * 540)
    assert (out / "index.html").exists() and rows[0]["slug"] in (out / "INDEX.md").read_text()
    assert (tmp_path / "export.zip").exists()


def test_llm_log_is_per_album(cfg, lib):
    def respond(name, payload):
        if name == "outline":
            return {"title": "T", "logline": "L", "pages": [{"shot": p["shot"], "position_id": p["position_id"], "beat": "",
                                                              "emotion": "a slow, heavy-lidded look", "detail": ""} for p in payload["pages"]]}
        return {"pages": [{"shot": p["shot"], "her": "She " + p["POSE HINT"], "emotion": "Her eyes are half-closed."}
                          for p in payload["pages"]]}

    class Logged(FakeLLM):
        def json(self, system, user, stage, name):
            self.log.append({"stage": name})
            return super().json(system, user, stage, name)

    llm = Logged(respond)
    llm.log = []
    mem = Memory(cfg.memory.db_path)
    first = make_album(cfg, llm=llm, library=lib, memory=mem)
    second = make_album(cfg, llm=llm, library=lib, memory=mem)
    for res in (first, second):
        logged = json.loads((res.dir / "plan.json").read_text())["llm"]
        assert 2 <= len(logged) <= 3, logged
