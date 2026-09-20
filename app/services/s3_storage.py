"""Small S3-compatible storage adapter used for provider reference images."""

import base64
import mimetypes
import urllib.request
import uuid
from typing import Optional
from urllib.parse import quote

from app.config import get_ai_config


def is_configured(cfg: Optional[dict] = None) -> bool:
    cfg = cfg or get_ai_config()
    return bool(
        cfg.get("s3_enabled")
        and cfg.get("s3_endpoint_url")
        and cfg.get("s3_bucket")
        and cfg.get("s3_access_key_id")
        and cfg.get("s3_secret_access_key")
    )


def _read_image(source: str, timeout: int = 30):
    if source.startswith("data:image/"):
        header, encoded = source.split(",", 1)
        mime = header.split(";", 1)[0][5:] or "png"
        return base64.b64decode(encoded), mime
    if source.startswith(("http://", "https://")):
        request = urllib.request.Request(source, headers={"User-Agent": "AI-Prompt-Studio/1.0"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get_content_type() or "image/png"
            return response.read(), content_type
    raise ValueError("Ảnh tham chiếu phải là data URI hoặc URL HTTP(S)")


def upload_reference_image(source: str, cfg: Optional[dict] = None) -> str:
    """Upload an image and return its public URL.

    boto3 is imported lazily so local-only installations keep working when S3
    is disabled.
    """
    cfg = cfg or get_ai_config()
    if not is_configured(cfg):
        raise RuntimeError("Chưa cấu hình đầy đủ S3-compatible storage")
    try:
        import boto3
    except ImportError as exc:
        raise RuntimeError("Thiếu thư viện boto3. Hãy cài dependencies của ứng dụng.") from exc

    content, mime = _read_image(source, timeout=int(cfg.get("timeout") or 30))
    extension = mimetypes.guess_extension(mime) or ".bin"
    if extension == ".jpe":
        extension = ".jpg"
    prefix = (cfg.get("s3_key_prefix") or "references").strip("/")
    key = f"{prefix + '/' if prefix else ''}{uuid.uuid4().hex}{extension}"
    client = boto3.client(
        "s3",
        endpoint_url=cfg["s3_endpoint_url"],
        region_name=cfg.get("s3_region") or "auto",
        aws_access_key_id=cfg["s3_access_key_id"],
        aws_secret_access_key=cfg["s3_secret_access_key"],
    )
    client.put_object(Bucket=cfg["s3_bucket"], Key=key, Body=content, ContentType=mime)
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": cfg["s3_bucket"], "Key": key},
        ExpiresIn=3600,
    )
