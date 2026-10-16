def test_references_resolve(lib):
    assert lib.check() == []


def test_never_regex(lib):
    r = lib.never_regex()
    assert r.search("a teen at school")
    assert r.search("her stepmom")
    assert not r.search("she climbs the steps of a staircase")
    assert not r.search("a patio with a hot tub")
