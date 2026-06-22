from app.dnflib_io import find_entry_index


class Entry:
    def __init__(self, name):
        self.name_str = name


def test_find_entry_index_matches_normalized_img_path():
    entries = [
        Entry("sprite/character/priest/effect/foo.img"),
        Entry(r"Sprite\Character\Priest\Effect\AtWeaponGuard\guard.img"),
    ]

    assert (
        find_entry_index(
            entries,
            "sprite/character/priest/effect/atweaponguard/guard.img",
        )
        == 1
    )


def test_find_entry_index_returns_none_when_missing():
    assert find_entry_index([Entry("sprite/a/b.img")], "sprite/a/c.img") is None
