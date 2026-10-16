import random
import re

from albumgen.compose import _side, assemble, fallback_fields, her_clothing, identity, shot1_prompt, surface
from albumgen.library import has_man
from albumgen.sampler import Sampler


def _plan(lib, mem, cfg, seed=5, **kw):
    return Sampler(lib, mem, cfg.album, cfg.memory, random.Random(seed)).plan(seed=seed, **kw)


def _pages(lib, mem, cfg, seeds=range(25), **kw):
    for seed in seeds:
        plan = _plan(lib, mem, cfg, seed=seed, **kw)
        for page in plan.pages:
            yield plan, page, lib.positions[page.position_id], assemble(plan, lib, page, fallback_fields(plan, lib, page))


def test_fixed_sentences(lib, mem, cfg):
    for plan, page, pos, text in _pages(lib, mem, cfg, range(6)):
        assert "Camera:" in text
        assert text.endswith("unretouched realistic photo, natural skin texture.")
        if pos.get("opening") != "action_first":
            assert text.startswith(identity(plan))
        if pos.get("beat") or plan.reference_mode == "ff":
            continue
        man_on = page.him_stage != "absent" and has_man(pos)
        assert ("She is alone in this shot" in text) == (not man_on)
        if man_on and pos.get("man_sentence") is not False:
            fixed = plan.man.face_sentence if plan.reference_mode == "couple" else plan.man.sentence
            assert fixed in text


def test_penetration_means_completely_naked(lib, mem, cfg):
    seen = 0
    for plan, page, pos, text in _pages(lib, mem, cfg):
        if pos.get("penetration"):
            seen += 1
            assert page.her_stage == "nude"
            assert "completely naked" in text and "vulva and buttocks fully bare" in text
            for part in plan.her_outfit.get("parts", []):
                assert f"wears the {part}" not in text and "in only the" not in text
    assert seen > 50


def test_cumshots_have_the_penis_out(lib, mem, cfg):
    for plan, page, pos, text in _pages(lib, mem, cfg):
        if page.position_id == "cum_on_back":
            assert "fully outside her body" in text
        if page.position_id == "cumshot_breasts_kneeling":
            assert "outside her body" in text


def test_clothing_never_comes_back_until_dressed_again(lib, mem, cfg):
    order = {"outfit": 0, "partial": 1, "underwear": 2, "topless": 3, "nude": 4}
    his_order = {"clothed": 0, "shirtless": 1, "nude": 2}
    for seed in range(40):
        plan = _plan(lib, mem, cfg, seed=seed)
        level = his = -1
        for page in plan.pages:
            if page.her_stage == "outfit_again":
                level = -1
                continue
            assert order[page.her_stage] >= level, (seed, page)
            level = order[page.her_stage]
            if page.him_stage != "absent":
                assert his_order[page.him_stage] >= his
                his = his_order[page.him_stage]


def test_pose_matches_clothing_stage(lib, mem, cfg):
    for seed in range(40):
        plan = _plan(lib, mem, cfg, seed=seed)
        for page in plan.pages:
            pos = lib.positions[page.position_id]
            if pos.get("stages") and not pos.get("penetration"):
                assert page.her_stage in pos["stages"], (page.position_id, page.her_stage)


def test_his_face_only_in_couple_mode(lib, mem, cfg):
    for seed in range(30):
        plan = _plan(lib, mem, cfg, seed=seed)
        if plan.reference_mode != "couple":
            for page in plan.pages:
                assert not lib.positions[page.position_id].get("needs_his_face")


def test_couple_mode(lib, mem, cfg):
    plan = _plan(lib, mem, cfg, mode="couple", theme_id="pizza_delivery")
    assert identity(plan).startswith("The reference photo shows the woman and the man of this album.")
    s1 = shot1_prompt(plan)
    assert "one adult woman and one adult man" in s1 and plan.his_outfit["phrase"] in s1


def test_solo_shot1(lib, mem, cfg):
    s1 = shot1_prompt(_plan(lib, mem, cfg, theme_id="boudoir_shoot"))
    assert "She is the only person in the photo." in s1 and "years old" in s1


def test_action_first_and_pov_exception(lib, mem, cfg):
    plan = _plan(lib, mem, cfg)
    page = plan.pages[8]
    page.position_id, page.him_stage, page.her_stage = "bed_edge_over_shoulder", "nude", "nude"
    text = assemble(plan, lib, page, {"her": "", "emotion": ""})
    assert text.startswith("Standing sex at the edge of a raised")
    assert "The woman is the woman from the reference photo" in text
    page.position_id = "oral_pov_sitting_bed_edge"
    text = assemble(plan, lib, page, {"her": "", "emotion": ""})
    assert plan.man.sentence not in text


def test_clothing_stages_and_grammar(lib, mem, cfg):
    plan = _plan(lib, mem, cfg)
    assert "completely naked" in her_clothing(plan, "nude")
    assert her_clothing(plan, "outfit").startswith("She wears")
    plan.her_outfit = {"phrase": "a grey uniform dress", "parts": ["uniform dress", "white lingerie"]}
    assert "uniform dress is off" in her_clothing(plan, "partial")
    plan.her_outfit = {"phrase": "jeans and a top", "parts": ["jeans", "top", "thong"]}
    assert "jeans are off" in her_clothing(plan, "partial")


def test_no_bed_words_without_a_bed(lib, mem, cfg):
    for theme in ("car_accident", "pool_cleaner_sunscreen", "oil_massage", "ff_pool_friends"):
        for seed in range(8):
            plan = _plan(lib, mem, cfg, seed=seed, theme_id=theme)
            if surface(plan) is None:
                continue
            for page in plan.pages:
                text = assemble(plan, lib, page, fallback_fields(plan, lib, page))
                assert not re.search(r"\bbed\b", text.lower()), text


def test_emotion_rules(lib):
    from albumgen.library import emotion_issues

    assert emotion_issues(lib, "sex", "She smiles widely.") != []
    assert emotion_issues(lib, "intro", "She laughs at his joke.") != []
    assert emotion_issues(lib, "intro", "She gives him a seductive half-smile.") == []
    assert emotion_issues(lib, "sex", "Her eyes are half-closed and her lips parted in a moan.") == []


def test_album_ends_naked_messy_with_semen(lib, mem, cfg):
    for seed in range(20):
        plan = _plan(lib, mem, cfg, seed=seed)
        last = plan.pages[-1]
        assert last.slot == "outro" and last.her_stage == "nude"
        text = assemble(plan, lib, last, fallback_fields(plan, lib, last))
        assert "hair messy" in text or "Both women look ravished" in text
        lpos = lib.positions[last.position_id]
        places = [lib.positions[p.position_id]["semen"] for p in plan.pages if lib.positions[p.position_id].get("semen")]
        assert len(places) <= 1  # one finish per album
        shows = lpos.get("shows", "all")
        seen = [x for x in places if shows == "all" or _side(x) == shows or (shows == "front" and _side(x) == "face")]
        if lpos.get("semen_carry") and seen:
            assert "White semen from earlier still glistens on her " + seen[0] in text
        if not seen:
            assert "White semen from earlier" not in text
        for word in ("laugh", "grin"):
            assert word not in text.lower()


def test_story_logic(lib, mem, cfg):
    for seed in range(30):
        plan = _plan(lib, mem, cfg, seed=seed)
        if plan.reference_mode == "couple":  # he never disappears in the middle of a meeting story
            assert all(p.slot != "solo" for p in plan.pages)
        if plan.reference_mode == "ff":
            assert plan.partner is not None and plan.partner.name != plan.character.name
            for page in plan.pages:
                text = assemble(plan, lib, page, fallback_fields(plan, lib, page))
                assert not re.search(r"\b(he|him|his|man|penis|semen)\b", text), (page.position_id, text)
                assert "{A}" not in text and "{B}" not in text


def test_outdoor_words(lib, mem, cfg):
    plan = _plan(lib, mem, cfg, seed=3, theme_id="car_accident")
    for page in plan.pages:
        text = assemble(plan, lib, page, fallback_fields(plan, lib, page))
        assert not re.search(r"\b(floor|pillows?|bed|sheet|rumpled car hood)\b", text), (page.position_id, text)


def test_repeat_takes_another_camera(lib, mem, cfg):
    plan = _plan(lib, mem, cfg, seed=1, theme_id="ff_roommates")
    seen = {}
    for page in plan.pages:
        pos = lib.positions[page.position_id]
        if page.take and pos.get("cameras"):
            text = assemble(plan, lib, page, fallback_fields(plan, lib, page))
            assert pos["camera"].split(",")[0] not in text or pos["cameras"][0].split(",")[0] in text
        seen[page.position_id] = seen.get(page.position_id, 0) + 1
    assert max(seen.values()) <= 2


def test_mature_and_busty_looks(lib, mem, cfg):
    for tid in ("mature_hotel_bar", "busty_bra_fitting"):
        plan = _plan(lib, mem, cfg, seed=2, theme_id=tid)
        look = plan.theme["look"]
        if look.get("age"):
            assert look["age"][0] <= plan.character.age <= look["age"][1]
        assert plan.character.figure == look["figure"]
        assert look.get("figure_short", look["figure"]) in identity(plan)


def test_unbuttoning_needs_a_shirt(lib, mem, cfg):
    for seed in range(60):
        plan = _plan(lib, mem, cfg, seed=seed)
        if any(p.position_id == "tease_unbutton_his_shirt" for p in plan.pages):
            assert re.search(r"(?<![\w-])shirt", plan.his_outfit["phrase"]), plan.his_outfit


def test_llm_pose_follows_the_place(lib, mem, cfg):
    plan = _plan(lib, mem, cfg, seed=3, theme_id="car_accident")
    page = next(p for p in plan.pages if p.slot == "sex")
    text = assemble(plan, lib, page, {"her": "She lies on the bed, her head on the pillow, feet on the floor.", "emotion": ""})
    assert "car hood" in text and not re.search(r"\b(bed|pillow|floor)\b", text)


def test_last_pages_lie_down_even_without_a_bed(lib, mem, cfg):
    for seed in range(12):
        plan = _plan(lib, mem, cfg, seed=seed, theme_id="couples_spa", arc_id="romantic")
        for page in plan.pages:
            if page.slot == "outro":
                assert lib.positions[page.position_id]["slot"] == "outro", page.position_id


def test_undressing_him_needs_trousers(lib, mem, cfg):
    for seed in range(20):
        plan = _plan(lib, mem, cfg, seed=seed, theme_id="couples_spa")
        if "robe" in plan.his_outfit["phrase"]:
            assert all(p.position_id != "undress_him" for p in plan.pages)


def test_two_women_clothes_only_come_off(lib, mem, cfg):
    order = ["partial", "underwear", "topless"]
    for tid in ("ff_roommates", "ff_pool_friends", "ff_lingerie_try_on", "ff_bridesmaids", "ff_neighbors_wine", "ff_massage"):
        for seed in range(4):
            plan = _plan(lib, mem, cfg, seed=seed, theme_id=tid)
            for k, outfit in enumerate((plan.her_outfit, plan.partner_outfit)):
                counts = []
                for st in order:
                    clause = her_clothing(plan, st).split(";")[k]  # one clause per woman
                    counts.append(sum(part in clause for part in outfit.get("parts", [])))
                assert counts == sorted(counts, reverse=True), (tid, outfit, counts)
