import os
import sys
import sqlite3
import argparse
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request
import urllib.error

# Ensure UTF-8 output on Windows consoles
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
IMAGES_DIR = DATA_DIR / "images"
DB_FILE = DATA_DIR / "prompts.db"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    "Accept-Language": "vi,en-US;q=0.9,en;q=0.8",
    "Referer": "https://www.facebook.com/"
}

def download_single_image(img_info, timeout=15, retries=2):
    img_id, prompt_id, url, filename = img_info
    target_path = IMAGES_DIR / filename

    if not url or not url.startswith("http"):
        return {"id": img_id, "status": "failed", "size": 0, "error": "Invalid URL"}

    req = urllib.request.Request(url, headers=HEADERS)

    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                content = response.read()
                if len(content) == 0:
                    raise ValueError("Empty response body")
                
                with open(target_path, "wb") as f:
                    f.write(content)

                return {
                    "id": img_id,
                    "status": "downloaded",
                    "size": len(content),
                    "local_path": f"images/{filename}",
                    "error": None
                }
        except Exception as e:
            if attempt == retries:
                return {
                    "id": img_id,
                    "status": "failed",
                    "size": 0,
                    "local_path": None,
                    "error": str(e)
                }
            time.sleep(1)

def run_download(workers=10, limit=None, timeout=15, force=False):
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    if not DB_FILE.exists():
        print(f"[!] Database not found at {DB_FILE}. Running migration first...")
        from scripts.migrate_json_to_sqlite import migrate
        migrate()

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    if force:
        cursor.execute("SELECT id, prompt_id, url, filename FROM images")
    else:
        cursor.execute("SELECT id, prompt_id, url, filename FROM images WHERE status != 'downloaded' OR local_path IS NULL")
    
    rows = cursor.fetchall()
    
    tasks = []
    skipped = 0
    for r in rows:
        img_id, prompt_id, url, filename = r
        if not filename:
            filename = f"{prompt_id}_img_{img_id}.jpg"
        
        file_path = IMAGES_DIR / filename
        if not force and file_path.exists() and file_path.stat().st_size > 500:
            cursor.execute("UPDATE images SET status = 'downloaded', local_path = ?, file_size = ? WHERE id = ?",
                           (f"images/{filename}", file_path.stat().st_size, img_id))
            skipped += 1
        else:
            tasks.append((img_id, prompt_id, url, filename))

    conn.commit()

    if limit and limit > 0:
        tasks = tasks[:limit]

    print("==================================================")
    print("  IMAGE DOWNLOADER - AI PROMPT STUDIO")
    print("==================================================")
    print(f" - Thư mục lưu ảnh : {IMAGES_DIR}")
    print(f" - Tổng số ảnh cần tải: {len(tasks)} (Đã có sẵn: {skipped})")
    print(f" - Số luồng đồng thời : {workers}")
    print(f" - Thời gian chờ timeout: {timeout}s")
    print("--------------------------------------------------")

    if not tasks:
        print("[+] Toàn bộ ảnh đã được tải về đầy đủ!")
        conn.close()
        return

    success_count = 0
    fail_count = 0

    pbar = tqdm(total=len(tasks), desc="Downloading", unit="img") if tqdm else None

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(download_single_image, task, timeout): task for task in tasks}

        for future in as_completed(futures):
            res = future.result()
            img_id = res["id"]
            status = res["status"]
            size = res["size"]
            local_path = res["local_path"]

            if status == "downloaded":
                success_count += 1
                cursor.execute("""
                    UPDATE images 
                    SET status = 'downloaded', local_path = ?, file_size = ?
                    WHERE id = ?
                """, (local_path, size, img_id))
            else:
                fail_count += 1
                cursor.execute("""
                    UPDATE images 
                    SET status = 'failed'
                    WHERE id = ?
                """, (img_id,))

            conn.commit()

            if pbar:
                pbar.update(1)
            else:
                print(f"[{success_count + fail_count}/{len(tasks)}] {res['status']}: ID {img_id}")

    if pbar:
        pbar.close()

    conn.close()

    print("\n==================================================")
    print("  KẾT QUẢ TẢI ẢNH:")
    print(f"  - Thành công: {success_count}")
    print(f"  - Thất bại  : {fail_count}")
    print(f"  - Đã có sẵn : {skipped}")
    print("==================================================")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tải toàn bộ ảnh prompt về máy cục bộ")
    parser.add_argument("-w", "--workers", type=int, default=10, help="Số luồng tải đồng thời (mặc định: 10)")
    parser.add_argument("-l", "--limit", type=int, default=None, help="Giới hạn số lượng ảnh tải")
    parser.add_argument("-t", "--timeout", type=int, default=15, help="Thời gian chờ (giây, mặc định: 15)")
    parser.add_argument("-f", "--force", action="store_true", help="Bắt buộc tải lại cả những ảnh đã có")

    args = parser.parse_args()
    run_download(workers=args.workers, limit=args.limit, timeout=args.timeout, force=args.force)
