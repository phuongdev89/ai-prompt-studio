import hashlib
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.config import get_ai_config
from app.services.s3_storage import (
    compute_md5,
    is_s3_url,
    upload_content_to_s3,
    upload_reference_image,
    save_koc_gallery_image,
    is_configured,
)

client = TestClient(app)

def test_compute_md5():
    data = b"hello test world"
    expected = hashlib.md5(data).hexdigest()
    assert compute_md5(data) == expected

def test_is_s3_url():
    cfg = get_ai_config()
    s3_url = "https://s3.us-west-004.backblazeb2.com/phuongdev89-affiliate/ai_prompts_database/abc123.jpg"
    assert is_s3_url(s3_url, cfg) is True
    assert is_s3_url("https://s3.amazonaws.com/mybucket/img.png", cfg) is True
    assert is_s3_url("images/prompt_2_img_1.jpg", cfg) is False
    assert is_s3_url("D:\\Affiliate\\img.jpg", cfg) is False

def test_s3_upload_content_live():
    cfg = get_ai_config()
    if not is_configured(cfg):
        return
    dummy_data = b"test content for unit test"
    res = upload_content_to_s3(content=dummy_data, filename="sample.png", mime="image/png", prefix="test_unit", cfg=cfg)
    assert res["status"] == "success"
    assert res["md5"] == hashlib.md5(dummy_data).hexdigest()
    assert res["filename"] == f"{res['md5']}.png"
    assert "test_unit/" in res["key"]
    assert res["url"].startswith("http")

def test_koc_draft_upload_live():
    cfg = get_ai_config()
    if not is_configured(cfg):
        return

    # Create a local temp file to simulate KOC image path
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(b"dummy koc image content")
        temp_path = f.name

    try:
        url = upload_reference_image(source=temp_path, cfg=cfg, is_koc=True)
        assert url.startswith("http")
        koc_prefix = cfg.get("s3_koc_prefix", "koc_management")
        # Ensure it went into draft subfolder
        assert f"{koc_prefix}/draft/" in url or "draft" in url

        # If already S3 link, it must return directly
        url2 = upload_reference_image(source=url, cfg=cfg, is_koc=True)
        assert url2 == url
    finally:
        try:
            Path(temp_path).unlink()
        except Exception:
            pass

def test_koc_gallery_save_live():
    cfg = get_ai_config()
    if not is_configured(cfg):
        return

    # Base64 test image (1x1 red PNG)
    b64_png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    res = save_koc_gallery_image(source=b64_png, koc_name="HaPhuong", cfg=cfg)
    assert res["status"] == "success"
    koc_prefix = cfg.get("s3_koc_prefix", "koc_management")
    assert f"{koc_prefix}/gallery/" in res["key"]
    assert res["filename"].endswith(".png")

def test_api_s3_upload():
    # Test JSON payload
    b64_png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    res = client.post("/api/s3/upload", json={"data": b64_png, "filename": "test_api.png"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["filename"].endswith(".png")

def test_api_koc_gallery_save(tmp_path):
    b64_png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    ref_file = tmp_path / "koc_character_ref.png"
    ref_file.write_bytes(b"dummy")

    res = client.post("/api/koc/gallery/save", json={
        "image": b64_png,
        "koc_name": "TestKOC",
        "ref_path": str(ref_file)
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "saved_path" in data
    assert Path(data["saved_path"]).is_file()
    assert Path(data["saved_path"]).parent == tmp_path

def test_koc_s3_mirror_structure(monkeypatch):
    import app.services.koc_service as ks
    sample_koc_data = {
        "Thu Trang": [
            {
                "name": "thu_trang_croptop_trang_chan_vay_be.png",
                "image": "https://s3.us-west-004.backblazeb2.com/phuongdev89-affiliate/koc_management/Thu%20Trang/thu_trang_croptop_trang_chan_vay_be.png?X-Amz-Expires=86400",
                "path": "https://s3.us-west-004.backblazeb2.com/phuongdev89-affiliate/koc_management/Thu%20Trang/thu_trang_croptop_trang_chan_vay_be.png?X-Amz-Expires=86400",
                "url": "https://s3.us-west-004.backblazeb2.com/phuongdev89-affiliate/koc_management/Thu%20Trang/thu_trang_croptop_trang_chan_vay_be.png?X-Amz-Expires=86400",
                "presigned_url": "https://s3.us-west-004.backblazeb2.com/phuongdev89-affiliate/koc_management/Thu%20Trang/thu_trang_croptop_trang_chan_vay_be.png?X-Amz-Expires=86400",
                "local_path": "D:\\Affiliate\\01_Brand_Assets\\AI_Character\\Thu Trang\\thu_trang_croptop_trang_chan_vay_be.png",
                "s3_path": "s3://phuongdev89-affiliate/koc_management/Thu Trang/thu_trang_croptop_trang_chan_vay_be.png",
                "s3_key": "koc_management/Thu Trang/thu_trang_croptop_trang_chan_vay_be.png",
                "rel_path": "thu_trang_croptop_trang_chan_vay_be.png",
                "caption": "Thu Trang mỉm cười rạng rỡ...",
                "id": "6de741491891",
                "media_type": "image"
            }
        ]
    }
    monkeypatch.setattr(ks, "get_cached_koc_data", lambda refresh=False: sample_koc_data)
    images = ks.get_images_for_koc("Thu Trang")
    assert len(images) == 1
    item = images[0]
    assert item["presigned_url"].startswith("https://s3")
    assert item["url"].startswith("https://s3")
    assert item["s3_path"].startswith("s3://")
    assert item["s3_key"] == "koc_management/Thu Trang/thu_trang_croptop_trang_chan_vay_be.png"
    assert item["local_path"].startswith("D:\\")
    # Verify backward compatibility when thumb is not in source: falls back to full image url
    assert item["thumb"] == item["url"]
    assert item["thumb_url"] == item["url"]


def test_koc_thumbnail_support(monkeypatch):
    import app.services.koc_service as ks
    sample_koc_data = {
        "Thu Trang": [
            {
                "name": "thu_trang_croptop_trang_chan_vay_be.png",
                "image": "https://s3.us-west-004.backblazeb2.com/phuongdev89-affiliate/koc_management/Thu%20Trang/thu_trang_croptop_trang_chan_vay_be.png?X-Amz-Expires=86400",
                "path": "https://s3.us-west-004.backblazeb2.com/phuongdev89-affiliate/koc_management/Thu%20Trang/thu_trang_croptop_trang_chan_vay_be.png?X-Amz-Expires=86400",
                "url": "https://s3.us-west-004.backblazeb2.com/phuongdev89-affiliate/koc_management/Thu%20Trang/thu_trang_croptop_trang_chan_vay_be.png?X-Amz-Expires=86400",
                "presigned_url": "https://s3.us-west-004.backblazeb2.com/phuongdev89-affiliate/koc_management/Thu%20Trang/thu_trang_croptop_trang_chan_vay_be.png?X-Amz-Expires=86400",
                "thumb": "https://s3.us-west-004.backblazeb2.com/phuongdev89-affiliate/koc_management/Thu%20Trang/thumbs/thu_trang_croptop_trang_chan_vay_be.png?X-Amz-Expires=86400",
                "thumb_url": "https://s3.us-west-004.backblazeb2.com/phuongdev89-affiliate/koc_management/Thu%20Trang/thumbs/thu_trang_croptop_trang_chan_vay_be.png?X-Amz-Expires=86400",
                "thumb_path": "https://s3.us-west-004.backblazeb2.com/phuongdev89-affiliate/koc_management/Thu%20Trang/thumbs/thu_trang_croptop_trang_chan_vay_be.png?X-Amz-Expires=86400",
                "thumb_rel_path": "thumbs/thu_trang_croptop_trang_chan_vay_be.png",
                "thumb_s3_key": "koc_management/Thu Trang/thumbs/thu_trang_croptop_trang_chan_vay_be.png",
                "local_path": "D:\\Affiliate\\01_Brand_Assets\\AI_Character\\Thu Trang\\thu_trang_croptop_trang_chan_vay_be.png",
                "s3_path": "s3://phuongdev89-affiliate/koc_management/Thu Trang/thu_trang_croptop_trang_chan_vay_be.png",
                "s3_key": "koc_management/Thu Trang/thu_trang_croptop_trang_chan_vay_be.png",
                "rel_path": "thu_trang_croptop_trang_chan_vay_be.png",
                "caption": "Thu Trang mỉm cười rạng rỡ...",
                "id": "6de741491891",
                "media_type": "image"
            }
        ]
    }
    monkeypatch.setattr(ks, "get_cached_koc_data", lambda refresh=False: sample_koc_data)
    images = ks.get_images_for_koc("Thu Trang")
    assert len(images) == 1
    item = images[0]
    assert "thumbs" in item["thumb"]
    assert "thumbs" in item["thumb_url"]
    assert item["thumb_rel_path"] == "thumbs/thu_trang_croptop_trang_chan_vay_be.png"
    assert item["thumb_s3_key"] == "koc_management/Thu Trang/thumbs/thu_trang_croptop_trang_chan_vay_be.png"
    # Full image URLs are intact
    assert item["image"].startswith("https://s3")
    assert "thumbs" not in item["image"]
    assert "thumbs" not in item["path"]

    # Verify summary list uses cover_thumb
    kocs = ks.get_koc_names_and_counts()
    assert len(kocs) == 1
    assert "thumbs" in kocs[0]["cover_thumb"]
    assert "thumbs" in kocs[0]["cover_url"]


def test_image_resize_to_480px():
    from PIL import Image
    import io
    from app.services.image_generator import resize_image_to_max_dimension

    # Create a 1000x2000 image
    large_img = Image.new("RGB", (1000, 2000), color=(255, 0, 0))
    buf = io.BytesIO()
    large_img.save(buf, format="JPEG")
    large_bytes = buf.getvalue()

    resized_bytes, ext, mime = resize_image_to_max_dimension(large_bytes, max_dim=480, default_ext="jpg")
    resized_img = Image.open(io.BytesIO(resized_bytes))
    w, h = resized_img.size

    # Height should be 480, width should be 240
    assert max(w, h) == 480
    assert h == 480
    assert w == 240
    assert len(resized_bytes) < len(large_bytes)



