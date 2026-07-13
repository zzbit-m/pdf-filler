import os
from pathlib import Path

DATA_BASE: Path = Path(os.environ.get("PDF_FILLER_DATA_DIR", "data"))
