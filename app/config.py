import os
from pathlib import Path

DATA_BASE = Path(os.environ.get("PBEAM_DATA_DIR", "data"))
