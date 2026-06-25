from pathlib import Path

from app.exporter import ExportJob, NpkExporter
from app.models import SkillRecord


class FakeNpkIO:
    def __init__(self, entries_by_npk):
        self.entries_by_npk = entries_by_npk
        self.written = []

    def read_entry(self, npk_path: Path, img_path: str) -> bytes:
        entries = self.entries_by_npk[npk_path.name]
        try:
            return entries[img_path]
        except KeyError:
            raise FileNotFoundError(f"IMG {img_path} not found in {npk_path}") from None

    def write_npk(self, output_path: Path, entries, overwrite: bool) -> None:
        self.written.append((output_path, list(entries), overwrite))


def make_skill(name, img_paths):
    return SkillRecord(
        sequence=1,
        big_profession="光职者(女)",
        small_profession="蓝拳使者(女)",
        chinese_name=name,
        english_name="sample",
        skill_type="原版",
        icon_img_path="sprite/character/priest/effect/atskillicon.img",
        icon_frame_index=80,
        img_paths=tuple(img_paths),
    )


def test_exporter_groups_images_by_rule_based_source_npk(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "sprite_character_priest_effect_atprayerofheal.NPK").write_bytes(b"npk")
    (source_dir / "sprite_common_commoneffect_wave.NPK").write_bytes(b"npk")

    io = FakeNpkIO(
        {
            "sprite_character_priest_effect_atprayerofheal.NPK": {
                "sprite/character/priest/effect/atprayerofheal/effect.img": b"effect",
            },
            "sprite_common_commoneffect_wave.NPK": {
                "sprite/common/commoneffect/wave/wave06.img": b"wave",
            },
        }
    )
    exporter = NpkExporter(io)
    skill = make_skill(
        "治愈祈祷",
        [
            "sprite/character/priest/effect/atskillicon.img",
            "sprite/common/commoneffect/wave/wave06.img",
            "sprite/character/priest/effect/atprayerofheal/effect.img",
        ],
    )

    report = exporter.export_skill(
        ExportJob(skill=skill, source_dir=source_dir, output_dir=tmp_path / "out")
    )

    assert report.output_path.name == "%治愈祈祷.npk"
    assert report.entry_count == 2
    assert len(io.written) == 1
    written_entries = io.written[0][1]
    assert written_entries == [
        ("sprite/common/commoneffect/wave/wave06.img", b"wave"),
        ("sprite/character/priest/effect/atprayerofheal/effect.img", b"effect"),
    ]


def test_exporter_reports_missing_rule_based_source_npk(tmp_path):
    io = FakeNpkIO({})
    exporter = NpkExporter(io)
    skill = make_skill(
        "缺失技能",
        ["sprite/character/archer/effect/centrifugalvenom/bodydeco01.img"],
    )

    report = exporter.export_skill(
        ExportJob(skill=skill, source_dir=tmp_path, output_dir=tmp_path / "out")
    )

    assert report.entry_count == 0
    assert report.missing_source_npks[0].npk_name == "sprite_character_archer_effect_centrifugalvenom.NPK"
    assert report.missing_source_npks[0].img_path == (
        "sprite/character/archer/effect/centrifugalvenom/bodydeco01.img"
    )


def test_exporter_skips_missing_source_npk_and_reports_it(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "sprite_character_thief_effect_yatagarasu.NPK").write_bytes(b"npk")

    io = FakeNpkIO(
        {
            "sprite_character_thief_effect_yatagarasu.NPK": {
                "sprite/character/thief/effect/yatagarasu/ember.img": b"ember",
            },
        }
    )
    exporter = NpkExporter(io)
    skill = make_skill(
        "火源限界·八咫乌",
        [
            "sprite/basic/floorring.img",
            "sprite/character/thief/effect/yatagarasu/ember.img",
        ],
    )

    report = exporter.export_skill(
        ExportJob(skill=skill, source_dir=source_dir, output_dir=tmp_path / "out")
    )

    assert report.entry_count == 1
    assert report.missing_source_npks[0].npk_name == "sprite_basic.NPK"
    assert report.missing_source_npks[0].img_path == "sprite/basic/floorring.img"
    assert io.written[0][1] == [
        ("sprite/character/thief/effect/yatagarasu/ember.img", b"ember"),
    ]


def test_exporter_skips_missing_img_entries_and_reports_them(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "sprite_character_thief_effect_yatagarasu.NPK").write_bytes(b"npk")

    io = FakeNpkIO(
        {
            "sprite_character_thief_effect_yatagarasu.NPK": {
                "sprite/character/thief/effect/yatagarasu/ember.img": b"ember",
            },
        }
    )
    exporter = NpkExporter(io)
    skill = make_skill(
        "缺一张图",
        [
            "sprite/character/thief/effect/yatagarasu/dummymotion.img",
            "sprite/character/thief/effect/yatagarasu/ember.img",
        ],
    )

    report = exporter.export_skill(
        ExportJob(skill=skill, source_dir=source_dir, output_dir=tmp_path / "out")
    )

    assert report.entry_count == 1
    assert report.missing_img_paths == (
        "sprite/character/thief/effect/yatagarasu/dummymotion.img",
    )
    assert io.written[0][1] == [
        ("sprite/character/thief/effect/yatagarasu/ember.img", b"ember"),
    ]
