import json
import sqlite3

from albumgen.llm import FakeLLM, extract_json
from albumgen.memory import Memory
from albumgen.pipeline import make_album


def test_extract_json():
    assert extract_json('Sure!\n```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('text {"pages": [1, 2]} more') == {"pages": [1, 2]}


def test_dry_run_writes_files_and_memory(cfg, lib):
    mem = Memory(cfg.memory.db_path)
    res = make_album(cfg, dry_run=True, library=lib, memory=mem)
    assert (res.dir / "album.json").exists() and (res.dir / "story.md").exists() and (res.dir / "plan.json").exists()
    reqs = json.loads((res.dir / "album.json").read_text())
    assert len(reqs) == 16 and reqs[0]["model"] == "qwen-image-3" and reqs[1]["params"]["images"]
    assert res.issues == {}
    assert mem.total() == 1


def test_no_theme_repeat_within_window_and_unique_faces(cfg, lib):
    mem = Memory(cfg.memory.db_path)
    themes, fps = [], set()
    for _ in range(12):
        res = make_album(cfg, dry_run=True, library=lib, memory=mem)
        themes.append(res.plan.theme["id"])
        fps.add(res.plan.character.fingerprint)
    for i in range(len(themes)):
        assert themes[i] not in themes[max(0, i - cfg.memory.theme_window):i]
    assert len(fps) == 12


def _responder(bad_shot=None, wrong_pose_shot=None):
    def respond(name, payload):
        if name == "outline":
            return {"title": "Late Delivery", "logline": "A late delivery turns into a long night.",
                    "pages": [{"shot": p["shot"], "position_id": p["position_id"], "beat": "They flirt.",
                               "emotion": "a heated, heavy-lidded look", "detail": ""} for p in payload["pages"]]}
        pages = []
        for p in payload["pages"]:
            her = "She " + p["POSE HINT"]
            if p["shot"] == bad_shot:
                her += " Her bra is on and his penis is close."  # code-owned words: must be rejected
            if p["shot"] == wrong_pose_shot:
                her = "She dances on the table."  # body position changed: must be rejected
            pages.append({"shot": p["shot"], "her": her, "emotion": "Her eyes are half-closed and her lips parted."})
        return {"pages": pages}
    return respond


def test_llm_path(cfg, lib):
    llm = FakeLLM(_responder())
    res = make_album(cfg, llm=llm, library=lib, memory=Memory(cfg.memory.db_path))
    assert set(res.sources.values()) == {"llm"}, res.sources
    assert res.issues == {}
    assert llm.calls == 2


def test_bad_fields_are_repaired_or_replaced(cfg, lib):
    from albumgen.writer import code_owned_pose
    for seed in range(50):  # an album where shots 5 and 7 are poses the LLM writes
        res = make_album(cfg, seed=seed, theme="boudoir_shoot", dry_run=True, save=False, library=lib,
                         memory=Memory(cfg.memory.db_path))
        if not any(code_owned_pose(lib.positions[p.position_id]) for p in res.plan.pages if p.shot in (5, 7)):
            break
    llm = FakeLLM(_responder(bad_shot=5, wrong_pose_shot=7))
    res = make_album(cfg, seed=seed, theme="boudoir_shoot", llm=llm, library=lib, memory=Memory(cfg.memory.db_path))
    assert res.issues == {}
    assert "bra is on" not in res.requests[4]["prompt"]
    assert "dances on the table" not in res.requests[6]["prompt"]
    assert res.sources[5].startswith("recipe") and res.sources[7].startswith("recipe")
    assert llm.calls == 3


def test_feedback_lowers_weight(cfg, lib):
    mem = Memory(cfg.memory.db_path)
    res = make_album(cfg, dry_run=True, library=lib, memory=mem)
    mem.add_feedback(res.album_id, [2, 3], "bad", "test")
    stats = mem.position_stats()
    assert stats[res.plan.pages[0].position_id][1] == 1


def test_outline_swaps_never_repeat_a_pose(cfg, lib):
    def respond(name, payload):
        if name == "outline":  # always asks for the first alternative, even if another page already has it
            return {"title": "Twin", "logline": "One night.",
                    "pages": [{"shot": p["shot"], "position_id": (p["alternatives"][0]["id"] if p["alternatives"] else p["position_id"]),
                               "beat": "", "emotion": "a heated, heavy-lidded look", "detail": ""} for p in payload["pages"]]}
        return {"pages": [{"shot": p["shot"], "her": "She " + p["POSE HINT"], "emotion": "Her eyes are half-closed."} for p in payload["pages"]]}
    for seed in range(5):
        res = make_album(cfg, seed=seed, llm=FakeLLM(respond), save=False, library=lib, memory=Memory(cfg.memory.db_path))
        ids = [p.position_id for p in res.plan.pages]
        sampled_repeats = len(ids) - len(set(ids))
        assert sampled_repeats <= sum(1 for p in res.plan.pages if p.take), ids


def test_a_refusing_or_broken_llm_still_gives_a_valid_album(cfg, lib):
    def refuse(name, payload):
        raise RuntimeError("I can't help with that request.")

    res = make_album(cfg, llm=FakeLLM(refuse), library=lib, memory=Memory(cfg.memory.db_path))
    assert res.issues == {} and len(res.requests) == 16
    assert res.outline["source"].startswith("default (LLM error")
    assert all(s.startswith("recipe") for s in res.sources.values())


def test_no_llm_configured_means_recipe_text(cfg, lib, monkeypatch):
    from albumgen.llm import make_llm

    monkeypatch.delenv(cfg.llm.api_key_env, raising=False)
    cfg.llm.model = ""
    assert make_llm(cfg.llm) is None
    res = make_album(cfg, library=lib, memory=Memory(cfg.memory.db_path))
    assert res.issues == {} and res.outline["source"] == "default"
