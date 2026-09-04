import json
import sqlite3
from typing import List, Dict, Any, Optional
from app.db.database import get_db

class PromptRepository:

    @staticmethod
    def get_prompts(query: Optional[str] = None, tag: str = "all", limit: Optional[int] = None, offset: int = 0) -> List[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Base query
            sql = """
                SELECT 
                    p.id, 
                    p.original_index, 
                    p.title, 
                    p.raw_title, 
                    p.prompt_type, 
                    p.raw_content,
                    p.prompt_code,
                    p.parsed_json,
                    p.created_at,
                    (SELECT COUNT(*) FROM images img WHERE img.prompt_id = p.id) as image_count
                FROM prompts p
                WHERE 1=1
            """
            params = []

            # Tag filters
            if tag == "has_img":
                sql += " AND (SELECT COUNT(*) FROM images img WHERE img.prompt_id = p.id) > 0"
            elif tag == "storyboard":
                sql += " AND (LOWER(p.title) LIKE '%storyboard%' OR LOWER(p.title) LIKE '%12 ô%' OR LOWER(p.title) LIKE '%12 khung%' OR LOWER(p.raw_content) LIKE '%storyboard%')"
            elif tag == "portrait":
                sql += " AND (LOWER(p.title) LIKE '%chân dung%' OR LOWER(p.title) LIKE '%gương mặt%' OR LOWER(p.title) LIKE '%gương mat%' OR LOWER(p.raw_content) LIKE '%portrait%' OR LOWER(p.raw_content) LIKE '%close-up%')"
            elif tag == "video":
                sql += " AND (LOWER(p.title) LIKE '%video%' OR LOWER(p.title) LIKE '%koc%' OR LOWER(p.raw_content) LIKE '%video%' OR LOWER(p.raw_content) LIKE '%scene 1%')"

            # Search query
            if query and query.strip():
                q_term = f"%{query.strip().lower()}%"
                sql += " AND (LOWER(p.title) LIKE ? OR LOWER(p.raw_content) LIKE ? OR LOWER(p.id) LIKE ?)"
                params.extend([q_term, q_term, q_term])

            sql += " ORDER BY p.original_index ASC"

            if limit is not None:
                sql += " LIMIT ? OFFSET ?"
                params.extend([limit, offset])

            cursor.execute(sql, params)
            prompts = cursor.fetchall()

            # Attach images list summary for each prompt in list view
            prompt_ids = [p["id"] for p in prompts]
            if prompt_ids:
                placeholders = ",".join("?" for _ in prompt_ids)
                cursor.execute(f"""
                    SELECT prompt_id, url, local_path, filename, status
                    FROM images
                    WHERE prompt_id IN ({placeholders})
                """, prompt_ids)
                img_rows = cursor.fetchall()
                img_map = {}
                for r in img_rows:
                    img_map.setdefault(r["prompt_id"], []).append(r)
                
                for p in prompts:
                    p["images"] = img_map.get(p["id"], [])
            else:
                for p in prompts:
                    p["images"] = []

            return prompts

    @staticmethod
    def get_prompt_by_id(prompt_id: str) -> Optional[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, original_index, title, raw_title, prompt_type, raw_content, prompt_code, parsed_json, created_at
                FROM prompts
                WHERE id = ?
            """, (prompt_id,))
            prompt = cursor.fetchone()
            if not prompt:
                return None

            # Parse parsed_json
            if prompt.get("parsed_json"):
                try:
                    prompt["parsed_json"] = json.loads(prompt["parsed_json"])
                except Exception:
                    pass

            # Fetch images
            cursor.execute("""
                SELECT id, prompt_id, url, local_path, filename, status, file_size
                FROM images
                WHERE prompt_id = ?
                ORDER BY id ASC
            """, (prompt_id,))
            prompt["images"] = cursor.fetchall()

            # Fetch fields
            cursor.execute("""
                SELECT id, prompt_id, field_path as path, field_key as key, label, field_value as value, field_type as type, is_list
                FROM prompt_fields
                WHERE prompt_id = ?
                ORDER BY id ASC
            """, (prompt_id,))
            fields = cursor.fetchall()
            for f in fields:
                f["is_list"] = bool(f.get("is_list", 0))
            prompt["fields"] = fields

            return prompt

    @staticmethod
    def update_prompt_json_structure(prompt_id: str, parsed_json: Dict[str, Any], prompt_code: str) -> bool:
        from app.services.parser import extract_flat_fields
        with get_db() as conn:
            cursor = conn.cursor()
            parsed_json_str = json.dumps(parsed_json, ensure_ascii=False)
            
            # Update prompt table
            cursor.execute("""
                UPDATE prompts 
                SET parsed_json = ?, prompt_code = ?, prompt_type = 'json'
                WHERE id = ?
            """, (parsed_json_str, prompt_code, prompt_id))

            # Delete old fields and insert new ones
            cursor.execute("DELETE FROM prompt_fields WHERE prompt_id = ?", (prompt_id,))
            new_fields = extract_flat_fields(parsed_json)
            for f in new_fields:
                cursor.execute("""
                    INSERT INTO prompt_fields (prompt_id, field_path, field_key, label, field_value, field_type, is_list)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    prompt_id,
                    f.get("path", ""),
                    f.get("key", ""),
                    f.get("label", ""),
                    str(f.get("value", "")),
                    f.get("type", "text"),
                    1 if f.get("is_list") else 0
                ))
            conn.commit()
            return True

    @staticmethod
    def update_prompt_title(prompt_id: str, title: str) -> bool:
        clean_title = (title or "").strip()
        if not clean_title:
            return False
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE prompts SET title = ? WHERE id = ?", (clean_title, prompt_id))
            conn.commit()
            return True

    @staticmethod
    def delete_prompt(prompt_id: str) -> bool:
        with get_db() as conn:
            cursor = conn.cursor()
            # Clean up local image files
            cursor.execute("SELECT filename FROM images WHERE prompt_id = ?", (prompt_id,))
            files = cursor.fetchall()
            from app.config import IMAGES_DIR
            for f in files:
                fname = f.get("filename")
                if fname:
                    fpath = IMAGES_DIR / fname
                    if fpath.exists():
                        try:
                            fpath.unlink()
                        except Exception:
                            pass

            cursor.execute("DELETE FROM prompts WHERE id = ?", (prompt_id,))
            deleted = cursor.rowcount > 0
            conn.commit()
            return deleted

    @staticmethod
    def get_stats() -> Dict[str, Any]:
        with get_db() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) as count FROM prompts")
            total_prompts = cursor.fetchone()["count"]

            cursor.execute("SELECT COUNT(*) as count FROM images")
            total_images = cursor.fetchone()["count"]

            cursor.execute("SELECT COUNT(*) as count FROM images WHERE status = 'downloaded'")
            downloaded_images = cursor.fetchone()["count"]

            cursor.execute("SELECT COUNT(*) as count FROM images WHERE status = 'pending'")
            pending_images = cursor.fetchone()["count"]

            cursor.execute("SELECT COUNT(*) as count FROM images WHERE status = 'failed'")
            failed_images = cursor.fetchone()["count"]

            cursor.execute("SELECT prompt_type, COUNT(*) as count FROM prompts GROUP BY prompt_type")
            by_type = {row["prompt_type"]: row["count"] for row in cursor.fetchall()}

            return {
                "total_prompts": total_prompts,
                "total_images": total_images,
                "downloaded_images": downloaded_images,
                "pending_images": pending_images,
                "failed_images": failed_images,
                "by_type": by_type
            }

    @staticmethod
    def create_prompt(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Find current max index
            cursor.execute("SELECT COUNT(*), MAX(original_index) FROM prompts")
            count_row = cursor.fetchone()
            total_count = count_row["COUNT(*)"] if "COUNT(*)" in count_row else count_row[list(count_row.keys())[0]]
            max_idx = count_row["MAX(original_index)"] if "MAX(original_index)" in count_row else 0
            if max_idx is None:
                max_idx = total_count

            new_idx = max_idx + 1
            new_id = f"prompt_{total_count + 1}"
            
            # Ensure unique id
            cursor.execute("SELECT id FROM prompts WHERE id = ?", (new_id,))
            while cursor.fetchone():
                new_idx += 1
                new_id = f"prompt_{new_idx}"
                cursor.execute("SELECT id FROM prompts WHERE id = ?", (new_id,))

            title = parsed_data.get("title") or f"Prompt #{new_idx}"
            raw_title = parsed_data.get("raw_title") or title
            prompt_type = parsed_data.get("prompt_type", "text")
            raw_content = parsed_data.get("raw_content", "")
            prompt_code = parsed_data.get("prompt_code", raw_content)
            parsed_json_str = json.dumps(parsed_data.get("parsed_json"), ensure_ascii=False) if parsed_data.get("parsed_json") else None

            # Insert prompt
            cursor.execute("""
                INSERT INTO prompts (id, original_index, title, raw_title, prompt_type, raw_content, prompt_code, parsed_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (new_id, new_idx, title, raw_title, prompt_type, raw_content, prompt_code, parsed_json_str))

            # Insert images
            for idx, img_url in enumerate(parsed_data.get("images", [])):
                if img_url and isinstance(img_url, str):
                    filename = f"{new_id}_img_{idx + 1}.jpg"
                    local_path = f"images/{filename}"
                    cursor.execute("""
                        INSERT INTO images (prompt_id, url, local_path, filename, status, file_size)
                        VALUES (?, ?, ?, ?, 'pending', 0)
                    """, (new_id, img_url, local_path, filename))

            # Insert fields
            for f in parsed_data.get("fields", []):
                cursor.execute("""
                    INSERT INTO prompt_fields (prompt_id, field_path, field_key, label, field_value, field_type, is_list)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    new_id,
                    f.get("path", ""),
                    f.get("key", ""),
                    f.get("label", ""),
                    str(f.get("value", "")),
                    f.get("type", "text"),
                    1 if f.get("is_list") else 0
                ))

            conn.commit()

        return PromptRepository.get_prompt_by_id(new_id)

    @staticmethod
    def add_image_to_prompt(prompt_id: str, filename: str, local_path: str, url: str = "", file_size: int = 0, status: str = "downloaded") -> bool:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO images (prompt_id, url, local_path, filename, status, file_size)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (prompt_id, url or filename, local_path, filename, status, file_size))
            conn.commit()
            return True
