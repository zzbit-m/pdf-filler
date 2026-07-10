from pathlib import Path

FONT_DIR = Path(__file__).resolve().parent.parent / "fonts"

_THAI_CANDIDATES = [
    "tahoma.ttf",
    "THSarabunNew.ttf",
    "THSarabun.ttf",
    "THSarabunPSK.ttf",
    "NotoSansThai-Regular.ttf",
    "NotoSerifThai-Regular.ttf",
]

_SYSTEM_THAI_FONTS = [
    "C:/Windows/Fonts/tahoma.ttf",
    "C:/Windows/Fonts/CordiaNew.ttf",
    "C:/Windows/Fonts/CordiaUPC.ttf",
    "C:/Windows/Fonts/AngsanaNew.ttf",
    "C:/Windows/Fonts/AngsanaUPC.ttf",
]


def get_font_path() -> str:
    for name in _THAI_CANDIDATES:
        path = FONT_DIR / name
        if path.exists():
            return str(path)
    for path_str in _SYSTEM_THAI_FONTS:
        path = Path(path_str)
        if path.exists():
            return str(path)
    msg = (
        f"No Thai-capable font found in {FONT_DIR} or system fonts. "
        "Download THSarabunNew.ttf (free license) and place it in app/fonts/"
    )
    raise FileNotFoundError(msg)
