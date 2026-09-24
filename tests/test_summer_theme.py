import json
from pathlib import Path

from sdhq_toolkit.gui import background, theme


def test_distribution_includes_summer_days_theme():
    root = Path(background.__file__).resolve().parents[3]
    config = root / "themes" / "summer_days" / "tema.json"
    image = root / "themes" / "summer_days" / "Fundo.jpg"
    logo = root / "themes" / "summer_days" / "Logo.jpg"

    assert config.is_file()
    assert image.is_file()
    assert logo.is_file()

    data = json.loads(config.read_text(encoding="utf-8"))
    assert data["id"] == "summer_days"
    assert data["nome"] == "Summer Days"
    assert data["index_keys"] == []
    assert data["opacidade"] == 1.0
    assert data["zoom"] == 1.0
    assert data["x"] == 0
    assert data["y"] == 0
    assert data["cores"]["red"].upper() == "#FB430B"


def test_summer_days_profile_uses_same_theme_loader_as_other_games():
    profile = theme.load_theme_profile(theme.SUMMER_THEME_ID, allow_root_override=False)
    assert profile["id"] == "summer_days"
    assert profile["nome"] == "Summer Days"
    assert Path(profile["_image_path"]).name == "Fundo.jpg"
    assert Path(profile["_logo_path"]).name == "Logo.jpg"
    assert profile["cores"]["navy"].upper() == "#201524"
