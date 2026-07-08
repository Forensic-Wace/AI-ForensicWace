"""Verification of previously generated, TSA-timestamped reports."""

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, UploadFile

from forensicwace_core.reporting import timestamping

from ..schemas import ReportVerification

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/verify", response_model=ReportVerification)
def verify_report(report: UploadFile, token: UploadFile):
    """Check a PDF report against its RFC 3161 ``.tsr`` timestamp token."""
    workdir = Path(tempfile.mkdtemp(prefix="fw-verify-"))
    try:
        report_path = workdir / "report.pdf"
        token_path = workdir / "report.tsr"
        report_path.write_bytes(report.file.read())
        token_path.write_bytes(token.file.read())
        return ReportVerification(verified=timestamping.verify(report_path, token_path))
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
