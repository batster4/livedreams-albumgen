from albumgen.validate import Validator


def test_rules(lib):
    v = Validator(lib, 23)
    ok = "The reference photo shows only the woman. Keep her exactly as in the reference: the same face; she is 30 years old. Camera: front view."
    assert v.prompt_issues(ok, 2) == []
    assert any("never-word" in i for i in v.prompt_issues(ok + " A young teen.", 2))
    assert any("negation" in i for i in v.prompt_issues(ok + " She wears no bra.", 2))
    assert any("age below" in i for i in v.prompt_issues(ok.replace("30", "20"), 2))
    assert v.prompt_issues("A photo. She is 30 years old. No text, no watermark.", 1) == []


def test_swaps(lib):
    assert Validator(lib).swap("a baby blue dress and baby oil") == "a pale blue dress and body oil"


def test_patient_monitor_is_equipment(lib):
    v = Validator(lib)
    assert v.text_issues("a hospital bed and a patient monitor") == []
    assert v.text_issues("she is a patient") != []
