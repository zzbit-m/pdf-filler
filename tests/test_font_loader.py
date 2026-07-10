from app.services.font_loader import get_font_path


def test_get_font_path_returns_existing_file() -> None:
    path = get_font_path()
    assert path is not None
    assert path.endswith(".ttf")
