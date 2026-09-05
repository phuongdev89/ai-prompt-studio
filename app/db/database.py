import sqlite3
import os
from contextlib import contextmanager
from app.config import DB_PATH, JSON_DATA_PATH

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = dict_factory
    # Enable foreign keys and WAL mode for faster concurrent reads
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

@contextmanager
def get_db():
    conn = get_db_connection()
    try:
        yield conn
    finally:
        conn.close()

def ensure_database():
    if not DB_PATH.exists():
        print(f"[!] Database not found at {DB_PATH}. Initializing and migrating...")
        from scripts.migrate_json_to_sqlite import migrate
        migrate(json_path=JSON_DATA_PATH, db_path=DB_PATH)
    else:
        # Check if tables exist
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='prompts'")
            if not cursor.fetchone():
                print("[!] Tables not found in database. Running migration...")
                from scripts.migrate_json_to_sqlite import migrate
                migrate(json_path=JSON_DATA_PATH, db_path=DB_PATH)

    # Ensure order_index column exists on images table
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(images)")
        cols = [c["name"] for c in cursor.fetchall()]
        if "order_index" not in cols:
            print("[*] Adding order_index column to images table...")
            cursor.execute("ALTER TABLE images ADD COLUMN order_index INTEGER DEFAULT 0")
            cursor.execute("UPDATE images SET order_index = id WHERE order_index = 0 OR order_index IS NULL")
            conn.commit()
