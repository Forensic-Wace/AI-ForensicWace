"""Image understanding: OCR and captioning.

Local pipeline: Tesseract (OCR) + LAVIS (caption) sidecars.
Cloud pipeline: Azure Computer Vision (both, in one call).
Results are stored on the message so they flow into the text analyzers.
"""

from functools import lru_cache
from pathlib import Path

import httpx

from ...config import get_settings
from ..types import AnalyzerStatus, Message

TIMEOUT = 120.0

_TESSERACT_OPTIONS = {"options": '{"languages":["eng"]}'}


def _post_image(endpoint: str, image_path: Path, data: dict) -> httpx.Response:
    with open(image_path, "rb") as image:
        return httpx.post(
            endpoint,
            data=data,
            files=[("file", (image_path.name, image, "image/jpeg"))],
            timeout=TIMEOUT,
        )


def _tesseract_ocr(image_path: Path) -> str:
    response = _post_image(get_settings().tesseract_endpoint, image_path, _TESSERACT_OPTIONS)
    response.raise_for_status()
    return response.json()["data"]["stdout"]


def _lavis_caption(image_path: Path) -> str:
    response = _post_image(get_settings().lavis_endpoint, image_path, {})
    response.raise_for_status()
    return response.json()["caption"]


@lru_cache
def _azure_client():
    from azure.ai.vision.imageanalysis import ImageAnalysisClient
    from azure.core.credentials import AzureKeyCredential

    settings = get_settings()
    return ImageAnalysisClient(endpoint=settings.ms_cv_endpoint, credential=AzureKeyCredential(settings.ms_cv_key))


def _azure_describe(image_path: Path) -> tuple[str | None, str | None]:
    from azure.ai.vision.imageanalysis.models import VisualFeatures

    with open(image_path, "rb") as f:
        image_data = f.read()

    result = _azure_client().analyze(
        image_data=image_data,
        visual_features=[VisualFeatures.CAPTION, VisualFeatures.READ],
        language=get_settings().ms_cv_language,
    )
    caption = result.caption.text if result.caption is not None else None
    ocr_text = None
    if result.read is not None and result.read.blocks:
        words = [word.text for line in result.read.blocks[0].lines for word in line.words]
        ocr_text = " ".join(words)
    return caption, ocr_text


def ocr_tesseract(message: Message) -> None:
    """Populate ``message.ocr_text`` via the Tesseract sidecar."""
    if message.media_path is not None and get_settings().tesseract_endpoint:
        message.ocr_text = _tesseract_ocr(message.media_path)


def caption_lavis(message: Message) -> None:
    """Populate ``message.caption`` via the LAVIS sidecar."""
    if message.media_path is not None and get_settings().lavis_endpoint:
        message.caption = _lavis_caption(message.media_path)


def describe_azure(message: Message) -> None:
    """Populate caption and OCR text via Azure Computer Vision (one call)."""
    if message.media_path is not None and get_settings().ms_cv_key:
        message.caption, message.ocr_text = _azure_describe(message.media_path)


def _test_image(name: str) -> Path | None:
    assets = get_settings().assets_dir
    if assets is None:
        return None
    candidate = assets / "analyzer_checks" / name
    return candidate if candidate.is_file() else None


def check_status_tesseract() -> AnalyzerStatus:
    if not get_settings().tesseract_endpoint:
        return AnalyzerStatus("Tesseract", False, "Endpoint not configured")
    image = _test_image("ImageOcrAnalyzerTest.png")
    if image is None:
        return AnalyzerStatus("Tesseract", True, "Configured (no test image available for a full check)")
    try:
        text = _tesseract_ocr(image)
        ok = "FORENSIC WACE" in text.strip()
        return AnalyzerStatus("Tesseract", ok, "Tesseract OCR is working" if ok else f"Unexpected OCR output: {text!r}")
    except Exception as exc:
        return AnalyzerStatus("Tesseract", False, str(exc))


def check_status_lavis() -> AnalyzerStatus:
    if not get_settings().lavis_endpoint:
        return AnalyzerStatus("Lavis", False, "Endpoint not configured")
    image = _test_image("ImageCaptionAnalyzerTest.PNG")
    if image is None:
        return AnalyzerStatus("Lavis", True, "Configured (no test image available for a full check)")
    try:
        caption = _lavis_caption(image)
        ok = any(word in caption for word in ("cat", "kitten", "bucket"))
        return AnalyzerStatus("Lavis", ok, "Lavis caption is working" if ok else f"Unexpected caption: {caption!r}")
    except Exception as exc:
        return AnalyzerStatus("Lavis", False, str(exc))


def check_status_microsoft() -> AnalyzerStatus:
    settings = get_settings()
    if not (settings.use_ms_ocr_caption and settings.ms_cv_key and settings.ms_cv_endpoint):
        return AnalyzerStatus("MS_CV", False, "Not enabled or not configured")
    image = _test_image("ImageCaptionAnalyzerTest.PNG")
    if image is None:
        return AnalyzerStatus("MS_CV", True, "Configured (no test image available for a full check)")
    try:
        caption, _ = _azure_describe(image)
        ok = caption is not None and "cat" in caption
        return AnalyzerStatus("MS_CV", ok, "Azure CV is working" if ok else f"Unexpected caption: {caption!r}")
    except Exception as exc:
        return AnalyzerStatus("MS_CV", False, str(exc))
