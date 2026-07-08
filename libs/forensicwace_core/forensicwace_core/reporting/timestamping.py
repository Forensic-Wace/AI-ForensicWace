"""RFC 3161 trusted timestamping of generated reports.

A report is timestamped by a remote TSA and shipped as a zip containing the
PDF plus the ``.tsr`` token, so anyone can later verify both integrity and
generation time.
"""

import tempfile
import zipfile
from pathlib import Path

import rfc3161ng

from ..config import get_settings
from ..exceptions import ConfigurationError


def _timestamper() -> rfc3161ng.RemoteTimestamper:
    settings = get_settings()
    if not settings.tsa_certificate_file or not Path(settings.tsa_certificate_file).is_file():
        raise ConfigurationError(
            "FW_TSA_CERTIFICATE_FILE must point to the TSA certificate used for timestamp verification"
        )
    certificate = Path(settings.tsa_certificate_file).read_bytes()
    return rfc3161ng.RemoteTimestamper(settings.tsa_url, certificate=certificate, hashname="sha256")


def sign_and_zip(pdf_bytes: bytes, base_name: str) -> Path:
    """Timestamp a PDF and bundle report + token into a zip in a temp dir."""
    out_dir = Path(tempfile.mkdtemp(prefix="fw-report-"))
    report_path = out_dir / f"{base_name}.pdf"
    token_path = out_dir / f"{base_name}.tsr"
    zip_path = out_dir / f"{base_name}.zip"

    report_path.write_bytes(pdf_bytes)
    token_path.write_bytes(_timestamper().timestamp(data=pdf_bytes))

    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.write(report_path, report_path.name)
        archive.write(token_path, token_path.name)

    report_path.unlink()
    token_path.unlink()
    return zip_path


def verify(report_path: Path | str, token_path: Path | str) -> bool:
    """Check a report against its timestamp token. False on any failure."""
    try:
        token = Path(token_path).read_bytes()
        data = Path(report_path).read_bytes()
        return bool(_timestamper().check(token, data=data))
    except Exception:
        return False
