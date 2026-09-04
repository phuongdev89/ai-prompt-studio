import json
import sqlite3
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
JSON_FILE = DATA_DIR / "cleaned_prompts.json"
DB_FILE = DATA_DIR / "prompts.db"

def init_db(conn: sqlite3.Connection):
    cursor = conn.cursor()
    
    # Table prompts
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prompts (
            id TEXT PRIMARY KEY,
            original_index INTEGER,
            title TEXT NOT NULL,
            raw_title TEXT,
            prompt_type TEXT,
            raw_content TEXT,
            prompt_code TEXT,
            parsed_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Table images
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt_id TEXT NOT NULL,
            url TEXT NOT NULL,
            local_path TEXT,
            filename TEXT,
            status TEXT DEFAULT 'pending',
            file_size INTEGER DEFAULT 0,
            FOREIGN KEY (prompt_id) REFERENCES prompts(id) ON DELETE CASCADE
        )
    """)
    
    # Table prompt_fields
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prompt_fields (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt_id TEXT NOT NULL,
            field_path TEXT,
            field_key TEXT,
            label TEXT,
            field_value TEXT,
            field_type TEXT DEFAULT 'text',
            is_list INTEGER DEFAULT 0,
            FOREIGN KEY (prompt_id) REFERENCES prompts(id) ON DELETE CASCADE
        )
    """)
    
    # Create indexes for fast lookup and search
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_prompts_title ON prompts(title);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_prompts_type ON prompts(prompt_type);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_prompt_id ON images(prompt_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_status ON images(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_fields_prompt_id ON prompt_fields(prompt_id);")
    
    conn.commit()

def migrate(json_path: Path = JSON_FILE, db_path: Path = DB_FILE, drop_existing: bool = True):
    if not json_path.exists():
        print(f"[ERROR] JSON file not found at: {json_path}")
        return False

    print(f"[*] Reading JSON data from: {json_path}")
    with open(json_path, 'r', encoding='utf-8') as f:
        prompts = json.load(f)

    print(f"[*] Connecting to SQLite database at: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    if drop_existing:
        cursor.execute("DROP TABLE IF EXISTS prompt_fields")
        cursor.execute("DROP TABLE IF EXISTS images")
        cursor.execute("DROP TABLE IF EXISTS prompts")
        conn.commit()

    init_db(conn)

    prompt_rows = []
    image_rows = []
    field_rows = []

    for item in prompts:
        p_id = item.get("id")
        orig_idx = item.get("original_index")
        title = item.get("title", "")
        raw_title = item.get("raw_title", "")
        prompt_type = item.get("prompt_type", "text")
        raw_content = item.get("raw_content", "")
        prompt_code = item.get("prompt_code", "")
        parsed_json_str = json.dumps(item.get("parsed_json"), ensure_ascii=False) if item.get("parsed_json") else None

        prompt_rows.append((
            p_id, orig_idx, title, raw_title, prompt_type, raw_content, prompt_code, parsed_json_str
        ))

        # Images
        for idx, img_url in enumerate(item.get("images", [])):
            if img_url and isinstance(img_url, str):
                filename = f"{p_id}_img_{idx + 1}.jpg"
                local_path = f"images/{filename}"
                img_disk_path = DATA_DIR / "images" / filename
                status = "downloaded" if img_disk_path.exists() else "pending"
                file_size = img_disk_path.stat().st_size if img_disk_path.exists() else 0

                image_rows.append((
                    p_id, img_url, local_path, filename, status, file_size
                ))

        # Fields
        for field in item.get("fields", []):
            field_rows.append((
                p_id,
                field.get("path", ""),
                field.get("key", ""),
                field.get("label", ""),
                str(field.get("value", "")),
                field.get("type", "text"),
                1 if field.get("is_list") else 0
            ))

    print(f"[*] Inserting {len(prompt_rows)} prompts...")
    cursor.executemany("""
        INSERT INTO prompts (id, original_index, title, raw_title, prompt_type, raw_content, prompt_code, parsed_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, prompt_rows)

    print(f"[*] Inserting {len(image_rows)} image records...")
    cursor.executemany("""
        INSERT INTO images (prompt_id, url, local_path, filename, status, file_size)
        VALUES (?, ?, ?, ?, ?, ?)
    """, image_rows)

    print(f"[*] Inserting {len(field_rows)} parameter fields...")
    cursor.executemany("""
        INSERT INTO prompt_fields (prompt_id, field_path, field_key, label, field_value, field_type, is_list)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, field_rows)

    conn.commit()
    conn.close()

    print(f"[SUCCESS] Migration completed successfully!")
    print(f" - Prompts: {len(prompt_rows)}")
    print(f" - Images:  {len(image_rows)}")
    print(f" - Fields:  {len(field_rows)}")
    return True

if __name__ == "__main__":
    migrate()
