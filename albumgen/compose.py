"""Builds the final prompt strings. Code owns every sentence that decides what the picture shows: the reference
and identity sentence, the camera, her clothing state, the act, the man (fixed sentence, state, place, hands,
framing) and the closing line. The LLM only writes her pose variation and her emotion. This keeps the rules that
made our tests pass impossible to break, and keeps the model from inventing clothing or anatomy.

Modes: solo (shot 1 = her alone; the story is told through his eyes), couple (shot 1 = the two of them meeting,
both faces; his face may appear later), ff (two women; {A} and {B} in recipes are filled with their names)."""

from __future__ import annotations

import re

from .library import Library, emotion_for, emotion_issues, has_man
from .sampler import Character, Page, Plan

UNDER = re.compile(r"bra|bralette|thong|panties|lingerie|teddy|bodysuit|chemise|nightie|stocking|garter|suspender|"
                   r"bodystocking|camisole|bikini|swimsuit|catsuit|towel|bathrobe|robe|shirt$|corset$", re.I)
BOTTOM = re.compile(r"thong|panties|bikini bottom|shorts|stocking|garter|suspender|bodystocking|swimsuit", re.I)
PLURAL = {"trousers", "shorts", "jeans", "leggings", "overalls", "coveralls", "stockings", "pants", "panties", "tights",
          "pantyhose", "wraps", "warmers", "boots", "heels", "gloves", "cuffs", "wings", "horns", "sandals", "sneakers",
          "glasses", "suspenders"}
CAMS = {
    "pair": "three-quarter view at chest height, about three metres away, both whole bodies in frame, both faces clearly visible",
    "pair_close": "three-quarter view at face height, both of them from the waist up, both faces clearly visible",
    "pair_seated": "three-quarter front view at seated eye level, both seated bodies in frame, both faces clearly visible",
    "pov": "first-person point-of-view shot from his eyes at standing height, her whole body in frame, she looks into the camera",
    "pov_seated": "first-person point-of-view shot from his eyes while he sits, her body from the top of her head to her knees in frame, she looks into the camera",
    "ff_pair": "three-quarter view at chest height, both women in frame, both faces clearly visible",
}


def _join(parts: list[str]) -> str:
    parts = [p for p in parts if p]
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def _are(parts: list[str]) -> str:
    if len(parts) > 1:
        return "are"
    last = parts[0].split()[-1].lower() if parts and parts[0].split() else ""
    return "are" if last in PLURAL or (last.endswith("s") and not last.endswith("ss")) else "is"


BARE_FEET = re.compile(r"\b(soles?|bare feet|bare foot|barefoot|toes)\b", re.I)
STOCKING = re.compile(r"stocking|tights|pantyhose|socks", re.I)


def _bare_pose(pos: dict | None) -> bool:
    text = " ".join(str((pos or {}).get(k, "")) for k in ("camera", "her", "act", "scene"))
    return bool(BARE_FEET.search(text)) and "stockinged" not in text


def _feet(plan: Plan, nude: bool = False, pos: dict | None = None) -> str:
    if _bare_pose(pos):
        return "barefoot"  # a feet pose: the shoes are off
    if not plan.footwear:
        return "barefoot"
    return f"except for her {plan.footwear}" if nude else f"in {plan.footwear}"


def her_clothing(plan: Plan, stage: str, pos: dict | None = None) -> str:
    """Authoritative clothing sentence for a page (in ff albums it covers both women)."""
    if pos and pos.get("clothing"):
        return pos["clothing"]
    phrase = plan.her_outfit["phrase"]
    parts: list[str] = list(plan.her_outfit.get("parts", []))
    ff = plan.reference_mode == "ff"
    if ff:
        other = (plan.partner_outfit or plan.her_outfit)["phrase"]
        a, b = plan.character.name if plan.partner else "", plan.partner.name if plan.partner else ""
        dressed = (f"{a[0].upper()}{a[1:]} wears {phrase}; {b} wears {other}; both are barefoot." if a and other != phrase
                   else f"Both women wear {phrase}, barefoot.")
        two = [(plan.character.name, plan.her_outfit), (plan.partner.name, plan.partner_outfit or plan.her_outfit)] if plan.partner else []

        def each(fn) -> str:
            text = "; ".join(fn(n, o) for n, o in two)
            return text[0].upper() + text[1:] + "; both are barefoot." if text else ""

        def kept(o: dict, stage_: str) -> list[str]:
            """What each woman still wears; every stage keeps only what the previous one kept."""
            ps = list(o.get("parts", [])) or [o["phrase"]]
            left = ps[1:] or ps  # partial: the first part is off
            if stage_ == "partial":
                return left
            left = [p for p in left if UNDER.search(p) or BOTTOM.search(p)] or left[-1:]
            if stage_ == "underwear":
                return left
            return [p for p in left if BOTTOM.search(p)] or left[-1:]  # topless: only the bottom stays

        both = {"outfit": dressed,
                "partial": each(lambda n, o: f"{n} still wears only her {_join(kept(o, 'partial'))}"),
                "underwear": each(lambda n, o: f"{n} is in only her {_join(kept(o, 'underwear'))}"),
                "topless": each(lambda n, o: f"{n} is topless, wearing only her {_join(kept(o, 'topless'))}"),
                "nude": "Both women are completely naked and barefoot, their clothes on the floor."}
        return both.get(stage) or both["nude"]
    feet = _feet(plan, False, pos)
    stripped = ""
    if _bare_pose(pos) and any(STOCKING.search(p) for p in parts) and stage != "nude":
        parts = [p for p in parts if not STOCKING.search(p)]  # a feet pose: the stockings are off too
        stripped = ", her stockings off"
    elif feet == "barefoot" and STOCKING.search(phrase):
        feet = ""  # stockinged feet are not bare
    feet = f"{stripped}, {feet}" if feet else stripped
    if stage == "outfit":
        return f"She wears the {_join(parts)}{feet}." if stripped else f"She wears {phrase}{feet}."
    if stage == "partial" and len(parts) > 1:
        return f"Her {parts[0]} {_are(parts[:1])} off; she still wears the {_join(parts[1:])}{feet}."
    if stage in ("underwear", "partial"):
        kept = parts[1:] if len(parts) > 1 else parts  # what came off at the partial stage stays off
        inner = [p for p in kept if UNDER.search(p)] or parts[-1:]
        outer = [p for p in parts if p not in inner]
        off = f"; the {_join(outer)} {_are(outer)} off" if outer else ""
        return f"She is in only the {_join(inner)}{off}{feet}."
    if stage == "topless":
        bottoms = [p for p in parts if BOTTOM.search(p)]
        sets = [p for p in parts if UNDER.search(p)]
        if not bottoms and sets:  # "black lace lingerie": she keeps its panties
            tops = [p for p in parts if p != sets[-1]]
            off = f"; the {_join(tops)} and the bra {_are(tops + ['bra'])} off" if tops else "; the bra is off"
            return f"She is topless{feet}, wearing only the panties of her {sets[-1]}{off}."
        bottoms = bottoms or ["small thong"]
        tops = [p for p in parts if p not in bottoms]
        off = f"; the {_join(tops)} {_are(tops)} off" if tops else ""
        return f"She is topless{feet}, wearing only the {_join(bottoms)}{off}."
    lie = "lie" if _are(parts) == "are" else "lies"
    off = f" her {_join(parts)} {lie} on the {ground(plan.location)} nearby," if parts else ""
    bare = ("her breasts, waist, hips, vulva and buttocks fully bare" if pos and pos.get("penetration")
            else "her breasts and body bare")
    naked = ("completely naked and barefoot" if _feet(plan, False, pos) == "barefoot"
             else f"completely naked {_feet(plan, True, pos)}")
    return f"She is {naked}:{off} {bare}."


def his_state(plan: Plan, stage: str, pos: dict) -> str:
    if stage == "clothed":
        return f"He is dressed in {plan.his_outfit['phrase']}."
    if stage == "shirtless":
        return "He is shirtless."
    if stage == "nude":
        if pos.get("man_full"):  # only parts of him are in frame: no body-hair words for parts out of frame
            return "He is fully nude."
        return f"He is fully nude, with {plan.man.nude_details}."
    return ""


SURFACES = ["daybed", "sunbed", "sun lounger", "lounger", "sofa", "massage table", "blanket", "towel", "rug", "cushions",
            "seat", "bench", "mattress", "rock ledge", "hood", "deck"]


def has_bed(location: dict) -> bool:
    return re.search(r"\bbed\b", f"{location['phrase']} {location['props']}".lower()) is not None


def surface(plan: Plan) -> str | None:
    """What she lies on when the location has no bed (None = it has a bed)."""
    if has_bed(plan.location):
        return None
    text = f"{plan.location['phrase']} {plan.location['props']}".lower()
    for s in SURFACES:
        if re.search(rf"\b{re.escape(s)}s?\b", text):
            return "car hood" if s == "hood" else s
    return "blanket"


OUTDOOR = [(r"\b(beach|sand|dunes?|shore)\b", "sand"),
           (r"\b(street|road|parking|garden|park|forest|woods|meadow|field|campsite|trail|lawn|yard|roadside)\b", "ground")]


def ground(location: dict) -> str:
    text = f"{location['phrase']} {location['props']}".lower()
    for rx, word in OUTDOOR:
        if re.search(rx, text):
            return word
    return "floor"


def fill(text: str, plan: Plan) -> str:
    rep = {"{his clothes}": plan.his_outfit["phrase"], "{his trousers}": "his trousers",
           "{outfit}": plan.her_outfit["phrase"], "{side}": "right", "{chair}": "chair", "{bed}": "bed"}
    if plan.partner is not None:
        rep["{A}"] = plan.character.name
        rep["{B}"] = plan.partner.name
    for k, v in rep.items():
        text = text.replace(k, v)
    text = re.sub(r"(^|[.]\s+)the (dark|blonde|red|silver|pink|auburn|brunette)", lambda m: m.group(1) + "The " + m.group(2), text)
    surf = surface(plan)
    if surf:
        text = text.replace("the headboard", "the backrest" if surf == "sofa" else f"the far edge of the {surf}")
        text = re.sub(r"\b(rumpled |raised |lowered |hospital )?bed\b", surf, text)
        text = re.sub(r"\b(rumpled )?(white )?(mattress|sheet)\b", surf, text)
        text = re.sub(r"\b(?:her|the) head on the pillows?\b", f"her head resting on the {surf}", text)
        text = re.sub(r"\bon the pillows? beside her head\b", "beside her head", text)
        text = re.sub(r"\b(the )?pillows?\b", f"the {surf}", text).replace("the the ", "the ")
    floor = ground(plan.location)
    if floor != "floor":
        text = re.sub(r"\bfloor\b", floor, text)
    return text


# ---------- shot 1 ----------
def _her_desc(c: Character, outfit: str, feet: str, subject: str = "She") -> str:
    worn = "glasses" in c.extra
    extra = f" {subject} has {c.extra}." if c.extra and not worn else ""
    wear = f" and {c.extra}" if worn else ""
    return (f"{subject} is {c.age} years old and {c.ethnicity}, with {c.skin} skin, {c.hair}, {c.eyes} eyes, defined brows "
            f"and {c.makeup}.{extra} {subject.replace('The woman', 'She')} has {c.figure}. "
            f"{subject.replace('The woman', 'She')} wears {outfit}{wear}, {feet}.")


def shot1_prompt(plan: Plan) -> str:
    c, m, loc = plan.character, plan.man, plan.location
    light = loc["light"][0].upper() + loc["light"][1:]
    scene = fill(plan.theme.get("shot1", ""), plan).strip()
    end = "Unretouched realistic photo, natural skin texture with visible pores. No text, no logos, no watermark."
    if plan.reference_mode == "ff" and plan.partner is not None:
        a, b = c, plan.partner
        desc_a = _her_desc(a, plan.her_outfit["phrase"], "barefoot", f"{a.name[0].upper()}{a.name[1:]}")
        desc_b = _her_desc(b, (plan.partner_outfit or plan.her_outfit)["phrase"], "barefoot", f"{b.name[0].upper()}{b.name[1:]}")
        desc_a = desc_a.replace(f"{a.name[0].upper()}{a.name[1:]} has", "She has").replace(f"{a.name[0].upper()}{a.name[1:]} wears", "She wears")
        desc_b = desc_b.replace(f"{b.name[0].upper()}{b.name[1:]} has", "She has").replace(f"{b.name[0].upper()}{b.name[1:]} wears", "She wears")
        scene = scene or f"{a.name[0].upper()}{a.name[1:]} and {b.name} kneel side by side on the bed facing the camera."
        return (f"A full-body vertical photograph of two adult women in {loc['phrase']}. {desc_a} {desc_b} {_sent(scene)} "
                f"The camera is at their chest height, about two and a half metres away, 50 mm lens, both whole bodies in "
                f"frame, both faces clearly visible and evenly lit, natural adult proportions. {light}, a little stronger "
                f"from the front left; {loc['props']} around them. {end} Exactly two women in the photo.")
    her = _her_desc(c, plan.her_outfit["phrase"], _feet(plan))
    if plan.reference_mode == "couple":
        man = (f"The man is in his {m.age_phrase}, with {m.build}, {m.hair_face} and {m.skin} skin; he wears "
               f"{plan.his_outfit['phrase']}.")
        scene = scene or ("She kneels upright and looks up at him with a calm, inviting expression; he stands in front of "
                          "her on the right of the photo, facing her, and looks down at her.")
        return (f"A full-body vertical photograph of one adult woman and one adult man in {loc['phrase']}. {her} {man} "
                f"{_sent(scene)} Camera: three-quarter view at chest height, about three metres away, 50 mm lens, both "
                f"whole bodies in frame from head to feet, both faces clearly visible and evenly lit, natural adult "
                f"proportions. {light}, a little stronger from the front left, with soft natural shadows; {loc['props']} "
                f"around them. {end}")
    if scene:
        return (f"A full-body vertical photograph of one adult woman alone in {loc['phrase']}. {her} {_sent(scene)} Her whole "
                f"face is clearly visible and evenly lit. The camera is at her eye level, about two metres away, 50 mm lens, "
                f"her whole body in frame, natural adult proportions. {light}, a little stronger from the front left, with "
                f"soft natural shadows; {loc['props']} around her. {end} She is the only person in the photo.")
    return (f"A full-body vertical photograph of one adult woman alone in {loc['phrase']}. {her} She kneels upright, "
            f"back straight, hands resting on her thighs, and looks up into the camera with a calm, inviting "
            f"expression; her whole face is clearly visible and evenly lit. The camera is slightly above her eye "
            f"level, about two metres away, 50 mm lens, her whole kneeling body in frame from the top of her head to "
            f"her knees and feet, natural adult proportions. {light}, a little stronger from the front left, with soft "
            f"natural shadows; {loc['props']} behind her. {end} She is the only person in the photo.")


# ---------- canvas pages ----------
def _look(c: Character) -> str:
    return f"the same face, {c.hair}, {c.skin} skin, {c.extra + ', ' if c.extra else ''}{c.figure_short} and {c.makeup_short}"


def identity(plan: Plan) -> str:
    c = plan.character
    if plan.reference_mode == "ff" and plan.partner is not None:
        b = plan.partner
        return (f"The reference photo shows the two women of this album. Keep both exactly as in the reference: {c.name} "
                f"is {c.age}, {c.ethnicity}, with {c.skin} skin, {c.hair}, {c.figure_short} and {c.makeup_short}; {b.name} "
                f"is {b.age}, {b.ethnicity}, with {b.skin} skin, {b.hair}, {b.figure_short} and {b.makeup_short}. They are "
                f"two different women.")
    if plan.reference_mode == "couple":
        m = plan.man
        return (f"The reference photo shows the woman and the man of this album. Keep both exactly as in the reference: "
                f"she has {_look(c)[len('the same face, '):]} and is {c.age} years old; he has {m.hair_face}, {m.build} "
                f"and {m.skin} skin.")
    return f"The reference photo shows only the woman. Keep her exactly as in the reference: {_look(c)}; she is {c.age} years old."


def tail(plan: Plan) -> str:
    return f"Same {plan.location['tail']} and {plan.location['light']}; unretouched realistic photo, natural skin texture."


def _sent(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    s = s[0].upper() + s[1:]
    return s if s.endswith((".", "!", "?")) else s + "."


def recipe_pose(plan: Plan, pos: dict) -> str:
    her = fill(str(pos.get("her", "")), plan).strip()
    if not her:
        return ""
    return _sent(her if pos.get("cast") == "ff" else f"She {her}")


def man_part(plan: Plan, page: Page, pos: dict) -> str:
    if page.him_stage == "absent" or not has_man(pos) or pos.get("beat"):
        return ""
    place = fill(str(pos.get("man", "")), plan).strip()
    place = _sent(place if pos.get("man_full") else f"He {place}")
    fixed = "" if pos.get("man_sentence") is False else (
        plan.man.face_sentence if plan.reference_mode == "couple" else plan.man.sentence)
    return " ".join(x for x in (fixed, his_state(plan, page.him_stage, pos), place) if x)


def history(plan: Plan, lib: Library, page: Page) -> tuple[bool, list[str]]:
    """(she has already had sex on an earlier page, places where semen landed on earlier pages)."""
    after_sex, semen = False, []
    for p in plan.pages:
        if p.shot >= page.shot:
            break
        pos = lib.positions[p.position_id]
        if pos.get("penetration") or p.slot in ("oral", "climax") or (pos.get("cast") == "ff" and p.slot == "sex"):
            after_sex = True
        if pos.get("semen") and pos["semen"] not in semen:
            semen.append(pos["semen"])
    return after_sex, semen


def _beat(plan: Plan, lib: Library, page: Page, pos: dict, emo: str) -> str:
    """A theme's own story page (the meeting, the first touch)."""
    cam = CAMS.get(pos.get("cam", "pair"), CAMS["pair"])
    if plan.reference_mode == "solo" and not pos.get("cam", "").startswith("pov"):
        cam = cam.replace(", both faces clearly visible", "") + "; the frame cuts him at the shoulders, his head outside the frame"
    scene = _sent(fill(pos.get("scene", ""), plan))
    man = ""
    if plan.reference_mode == "couple" and page.him_stage != "absent":
        man = f"{plan.man.face_sentence} {his_state(plan, page.him_stage, pos)}"
    parts = [identity(plan), "Camera, pose and clothing follow the text below.", _sent(f"Camera: {cam}"),
             her_clothing(plan, page.her_stage, pos), scene, emo, man, tail(plan)]
    return re.sub(r"\s+", " ", " ".join(p for p in parts if p)).strip()


def _side(place: str) -> str:
    return "back" if re.search(r"\b(back|buttocks)\b", place) else "face" if re.search(r"\b(face|chin|lips|tongue)\b", place) else "front"


def assemble(plan: Plan, lib: Library, page: Page, fields: dict) -> str:
    """fields: {"her": her pose sentence(s) from the LLM or "", "emotion": one sentence or ""}."""
    pos = lib.positions[page.position_id]
    ff = plan.reference_mode == "ff"
    eslot = pos.get("emotion_slot", page.slot)
    emo = _sent(fields.get("emotion", ""))
    if ff or not emo or emotion_issues(lib, eslot, emo) or (eslot != page.slot and emotion_issues(lib, page.slot, emo)):
        emo = emotion_for(lib, eslot, page.shot, ff)
    if pos.get("emotion"):  # a pose with its own fixed face (a kiss)
        emo = _sent(pos["emotion"])
    if pos.get("beat"):
        return _beat(plan, lib, page, pos, emo)
    after_sex, semen = history(plan, lib, page)
    used = ""
    if after_sex and page.her_stage == "nude" and lib.emotions.get("after_sex_look"):
        look = lib.emotions["after_sex_look"]
        used = _sent(("Both women look ravished: " + look.replace("her ", "their ")) if ff else "Her look shows what happened: " + look)
    shows = pos.get("shows", "all")
    seen = [s for s in semen if shows == "all" or _side(s) == shows or (shows == "front" and _side(s) == "face")]
    if seen and (pos.get("semen_carry") or page.slot == "climax"):
        used += " " + _sent("White semen from earlier still glistens on her " + " and on her ".join(seen))
    cam = pos.get("camera", "three-quarter view at chest height, her whole body in frame")
    if page.take and pos.get("cameras"):
        cam = pos["cameras"][(page.take - 1) % len(pos["cameras"])]
    camera = _sent("Camera: " + fill(cam, plan).rstrip("."))
    clothing = her_clothing(plan, page.her_stage, pos)
    pose = recipe_pose(plan, pos) if ff else (_sent(fill(fields.get("her", ""), plan)) or recipe_pose(plan, pos))
    act = _sent(fill(pos.get("act", ""), plan))
    man = man_part(plan, page, pos)
    if ff:
        solo = _sent(f"Exactly two women in the photo, {plan.character.name} and {plan.partner.name}") if plan.partner else ""
    else:
        solo = "" if man else ("She is alone in this shot; he is outside the frame." if plan.reference_mode == "couple"
                               else "She is alone in this shot.")
    if pos.get("opening") == "action_first" and not ff:
        action = _sent(fill(pos.get("action_line", ""), plan))
        who = f"The woman is the woman from the reference photo: {_look(plan.character)}; she is {plan.character.age} years old."
        parts = [action, who, camera, solo, clothing, used, pose, act, emo, man, tail(plan)]
    else:
        parts = [identity(plan), "Camera, pose and clothing follow the text below.", camera, solo, clothing, used, pose,
                 act, emo, man, tail(plan)]
    return re.sub(r"\s+", " ", " ".join(p for p in parts if p)).strip()


def fallback_fields(plan: Plan, lib: Library, page: Page, emotion: str = "") -> dict:
    """Deterministic page text from the position recipe: always valid, less varied."""
    emo = (emotion or "").strip()
    if emo and not emo.lower().startswith(("she ", "her ")):
        emo = f"She shows {emo}"
    return {"her": recipe_pose(plan, lib.positions[page.position_id]), "emotion": emo}
