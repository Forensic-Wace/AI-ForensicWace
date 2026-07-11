import os
from pathlib import Path

REPO_ROOT = Path(__file__).parents[3]
os.environ.setdefault("FW_SCHEMAS_DIR", str(REPO_ROOT / "schemas" / "whatsapp"))
# The API test-suite exercises features, not the session layer; the auth
# tests (test_auth_api.py) re-enable it explicitly.
os.environ.setdefault("FW_AUTH_DISABLED", "true")
