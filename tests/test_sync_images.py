import io
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError

from app.services.sync_manager import _download_images_bg


class SyncImageTests(unittest.TestCase):
    def test_background_download_success_and_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / 'test.db'
            with closing(sqlite3.connect(db_path)) as conn:
                conn.execute('''CREATE TABLE images (
                    id INTEGER PRIMARY KEY, prompt_id TEXT, url TEXT,
                    local_path TEXT, filename TEXT, status TEXT,
                    order_index INTEGER, file_size INTEGER)''')
            response = io.BytesIO(b'image-fixture')
            response.headers = {'Content-Type': 'image/png'}
            with patch('app.db.database.DB_PATH', db_path), \
                 patch('app.services.downloader.IMAGES_DIR', Path(tmp) / 'images'), \
                 patch('app.services.downloader.time.sleep'), \
                 patch('app.services.downloader.urllib.request.urlopen',
                       side_effect=[response, URLError('offline'), URLError('offline')]):
                _download_images_bg([
                    ('p1', 'https://example.invalid/ok.png', 2),
                    ('p1', 'https://example.invalid/fail.png', 3),
                ])
            with closing(sqlite3.connect(db_path)) as conn:
                rows = conn.execute('SELECT status, local_path, order_index FROM images ORDER BY id').fetchall()
            self.assertEqual(rows[0], ('downloaded', 'images/p1_img_1.png', 2))
            self.assertEqual(rows[1], ('failed', None, 3))
            self.assertEqual((Path(tmp) / rows[0][1]).read_bytes(), b'image-fixture')
