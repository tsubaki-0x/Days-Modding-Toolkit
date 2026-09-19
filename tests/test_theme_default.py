import json
from pathlib import Path
from unittest import mock

from sdhq_toolkit.gui import background, theme


def test_distribution_includes_default_school_days_theme():
    root = Path(background.__file__).resolve().parents[3]
    config = root / "themes" / "school_days" / "tema.json"
    image = root / "themes" / "school_days" / "Fundo.png"
    logo = root / "themes" / "school_days" / "Logo.png"
    assert config.is_file()
    assert image.is_file()
    assert logo.is_file()
    data = json.loads(config.read_text(encoding="utf-8"))
    assert data["id"] == "school_days"
    assert data["index_keys"] == ["SCHOOL_DAYS_HQ"]
    assert data["opacidade"] == 1.0
    assert data["zoom"] == 1.0
    assert data["x"] == 50
    assert data["y"] == 0


def test_distribution_includes_shiny_days_theme():
    root = Path(background.__file__).resolve().parents[3]
    config = root / "themes" / "shiny_days" / "tema.json"
    image = root / "themes" / "shiny_days" / "Fundo.png"
    logo = root / "themes" / "shiny_days" / "Logo.png"
    assert config.is_file()
    assert image.is_file()
    assert logo.is_file()
    data = json.loads(config.read_text(encoding="utf-8"))
    assert data["id"] == "shiny_days"
    assert data["index_keys"] == ["SHINY_DAYS"]
    assert data["opacidade"] == 1.0
    assert data["zoom"] == 1.0
    assert data["x"] == 0
    assert data["y"] == 0
    assert data["cores"]["red"].upper().startswith("#F")
    assert data["cores"]["light"].upper().startswith("#FF")


def test_game_key_maps_to_expected_theme():
    assert theme.theme_for_index_key("SCHOOL_DAYS_HQ") == "school_days"
    assert theme.theme_for_index_key("SHINY_DAYS") == "shiny_days"
    assert theme.theme_for_index_key("NO_XOR") is None


def test_artwork_image_is_resolved_beside_tema_json(tmp_path):
    image = tmp_path / "custom.png"
    image.write_bytes(b"png-placeholder")
    config = tmp_path / "tema.json"
    config.write_text('{"imagem":"custom.png","opacidade":0.5}', encoding="utf-8")
    real_project = theme.project_root()
    with mock.patch.object(theme, "project_root", return_value=real_project), \
         mock.patch.object(Path, "cwd", return_value=tmp_path):
        profile = theme.load_theme_profile("school_days")
    assert profile["opacidade"] == 0.5
    assert Path(profile["_image_path"]) == image.resolve()


def test_artwork_panel_does_not_shadow_tkinter_root_method():
    import inspect
    source = inspect.getsource(background.ArtworkPanel)
    assert "self._root =" not in source
    assert "self._host_root =" in source
