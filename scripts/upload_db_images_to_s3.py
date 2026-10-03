"""Script to upload all existing local images in DB to S3 using MD5 hash filenames.
Updates SQLite database records with direct S3 URLs.
"""
import sys
import os

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import get_ai_config
from app.services.s3_storage import migrate_all_db_images_to_s3, is_configured

def main():
    cfg = get_ai_config()
    print("=== AI Prompts Database: Migrate All DB Images to S3 ===")
    print("S3 Enabled    :", cfg.get("s3_enabled"))
    print("S3 Endpoint   :", cfg.get("s3_endpoint_url"))
    print("S3 Bucket     :", cfg.get("s3_bucket"))
    print("S3 Key Prefix :", cfg.get("s3_key_prefix"))

    if not is_configured(cfg):
        print("[!] Lỗi: S3 chưa được cấu hình đầy đủ trong file .env!")
        sys.exit(1)

    print("\nĐang tiến hành đọc DB và tải ảnh lên S3 (sử dụng md5_file)...")
    res = migrate_all_db_images_to_s3(cfg)

    print("\n=== Kết quả di chuyển ảnh lên S3 ===")
    print(f"Tổng số ảnh trong DB: {res.get('total')}")
    print(f"Đã upload thành công : {res.get('uploaded')}")
    print(f"Bỏ qua (đã có trên S3): {res.get('skipped')}")
    print(f"Lỗi                  : {res.get('errors')}")

    if res.get("error_details"):
        print("\nChi tiết lỗi:")
        for err in res["error_details"]:
            print(f"  - ID {err.get('id')}: {err.get('error')}")

    print("\nHoàn tất!")

if __name__ == "__main__":
    main()
