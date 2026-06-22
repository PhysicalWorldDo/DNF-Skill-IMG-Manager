from pathlib import Path

import pytest

from app.npk_paths import (
    img_path_to_npk_name,
    normalize_img_path,
    sanitize_windows_filename,
    skill_output_filename,
)


def test_img_path_to_npk_name_uses_parent_directory_segments():
    assert (
        img_path_to_npk_name(
            "sprite/character/archer/effect/centrifugalvenom/bodydeco01.img"
        )
        == "sprite_character_archer_effect_centrifugalvenom.NPK"
    )


def test_img_path_to_npk_name_normalizes_backslashes_and_case():
    assert (
        img_path_to_npk_name(
            r"Sprite\Character\Priest\Effect\AtPrayerOfHeal\effect.img"
        )
        == "sprite_character_priest_effect_atprayerofheal.NPK"
    )


def test_img_path_to_npk_name_rejects_paths_without_parent():
    with pytest.raises(ValueError, match="parent directory"):
        img_path_to_npk_name("effect.img")


def test_normalize_img_path_trims_and_uses_forward_slashes():
    assert normalize_img_path(r"  SPRITE\A\b.img  ") == "sprite/a/b.img"


def test_skill_output_filename_sanitizes_windows_reserved_characters():
    assert (
        skill_output_filename('黄泉之门 : "万鬼度灵"')
        == "%黄泉之门 ： ＂万鬼度灵＂.npk"
    )


def test_sanitize_windows_filename_falls_back_for_blank_name():
    assert sanitize_windows_filename("   ...  ") == "unnamed"
