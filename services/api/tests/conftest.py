import os
from pathlib import Path

REPO_ROOT = Path(__file__).parents[3]
os.environ.setdefault("FW_SCHEMAS_DIR", str(REPO_ROOT / "schemas" / "whatsapp"))
