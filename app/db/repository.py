import json
import sqlite3
from typing import List, Dict, Any, Optional, Tuple
from app.db.database import get_db
from app.services.label_mapping import format_field_label, detect_primary_fields

class PromptRepository:

    @staticmethod
    def get_prompts(query: Optional[str] = None, tag: str = "all", category: Optional[str] = "image", limit: Optional[int] = None, offset: int = 0) -> List[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Map legacy 'character' alias to 'image'
            cat_filter = category
            if cat_filter == "character":
                cat_filter = "image"

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
                    p.category,
                    p.note,
                    p.created_at,
                    (SELECT COUNT(*) FROM images img WHERE img.prompt_id = p.id) as image_count,
                    (SELECT COUNT(*) FROM sample_contents sc WHERE sc.prompt_id = p.id) as sample_count
                FROM prompts p
                WHERE 1=1
            """
            params = []

            # Category filter
            if cat_filter:
                sql += " AND p.category = ?"
                params.append(cat_filter)

            # Tag filters
            if tag == "has_img":
                sql += " AND (SELECT COUNT(*) FROM images img WHERE img.prompt_id = p.id) > 0"
            elif tag == "no_img":
                sql += " AND (SELECT COUNT(*) FROM images img WHERE img.prompt_id = p.id) = 0"
            elif tag == "has_sample":
                sql += " AND (SELECT COUNT(*) FROM sample_contents sc WHERE sc.prompt_id = p.id) > 0"
            elif tag == "storyboard":
                sql += " AND (LOWER(p.title) LIKE '%storyboard%' OR LOWER(p.title) LIKE '%12 ô%' OR LOWER(p.title) LIKE '%12 khung%' OR LOWER(p.raw_content) LIKE '%storyboard%')"
            elif tag == "portrait":
                sql += " AND (LOWER(p.title) LIKE '%chân dung%' OR LOWER(p.title) LIKE '%gương mặt%' OR LOWER(p.title) LIKE '%gương mat%' OR LOWER(p.raw_content) LIKE '%portrait%' OR LOWER(p.raw_content) LIKE '%close-up%')"
            elif tag == "video":
                sql += " AND (LOWER(p.title) LIKE '%video%' OR LOWER(p.title) LIKE '%koc%' OR LOWER(p.raw_content) LIKE '%video%' OR LOWER(p.raw_content) LIKE '%scene 1%')"
            elif tag == "seo":
                sql += " AND (LOWER(p.title) LIKE '%seo%' OR LOWER(p.note) LIKE '%seo%' OR LOWER(p.raw_content) LIKE '%seo%')"
            elif tag == "live":
                sql += " AND (LOWER(p.title) LIKE '%live%' OR LOWER(p.note) LIKE '%live%' OR LOWER(p.raw_content) LIKE '%live%')"
            elif tag == "json":
                sql += " AND (p.prompt_type = 'json' OR p.parsed_json IS NOT NULL)"
            elif tag == "text":
                sql += " AND (p.prompt_type != 'json' OR p.parsed_json IS NULL)"
            elif tag and tag != "all":
                sql += " AND EXISTS (SELECT 1 FROM prompt_tags pt WHERE pt.prompt_id = p.id AND LOWER(pt.tag) = LOWER(?))"
                params.append(tag)

            # Search query (matches title, content, note, id, tags)
            if query and query.strip():
                q_term = f"%{query.strip().lower()}%"
                sql += """ AND (
                    LOWER(p.title) LIKE ? 
                    OR LOWER(p.raw_content) LIKE ? 
                    OR LOWER(p.id) LIKE ? 
                    OR LOWER(COALESCE(p.note, '')) LIKE ?
                    OR EXISTS (SELECT 1 FROM prompt_tags pt WHERE pt.prompt_id = p.id AND LOWER(pt.tag) LIKE ?)
                )"""
                params.extend([q_term, q_term, q_term, q_term, q_term])

            sql += " ORDER BY p.original_index ASC"

            if limit is not None:
                sql += " LIMIT ? OFFSET ?"
                params.extend([limit, offset])

            cursor.execute(sql, params)
            prompts = cursor.fetchall()

            # Attach images and tags list summary for each prompt in list view
            prompt_ids = [p["id"] for p in prompts]
            if prompt_ids:
                placeholders = ",".join("?" for _ in prompt_ids)
                cursor.execute(f"""
                    SELECT prompt_id, url, local_path, filename, status, order_index
                    FROM images
                    WHERE prompt_id IN ({placeholders})
                    ORDER BY order_index ASC, id ASC
                """, prompt_ids)
                img_rows = cursor.fetchall()
                img_map = {}
                for r in img_rows:
                    img_map.setdefault(r["prompt_id"], []).append(r)

                cursor.execute(f"""
                    SELECT prompt_id, tag
                    FROM prompt_tags
                    WHERE prompt_id IN ({placeholders})
                    ORDER BY id ASC
                """, prompt_ids)
                tag_rows = cursor.fetchall()
                tag_map = {}
                for r in tag_rows:
                    tag_map.setdefault(r["prompt_id"], []).append(r["tag"])

                for p in prompts:
                    p["images"] = img_map.get(p["id"], [])
                    p["tags"] = tag_map.get(p["id"], [])
            else:
                for p in prompts:
                    p["images"] = []
                    p["tags"] = []

            return prompts

    @staticmethod
    def get_prompt_by_id(prompt_id: str) -> Optional[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, original_index, title, raw_title, prompt_type, raw_content, prompt_code, parsed_json, category, note, created_at
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
                SELECT id, prompt_id, url, local_path, filename, status, file_size, order_index
                FROM images
                WHERE prompt_id = ?
                ORDER BY order_index ASC, id ASC
            """, (prompt_id,))
            prompt["images"] = cursor.fetchall()

            # Fetch sample contents
            cursor.execute("""
                SELECT id, prompt_id, content, title, order_index, created_at
                FROM sample_contents
                WHERE prompt_id = ?
                ORDER BY order_index ASC, id ASC
            """, (prompt_id,))
            prompt["sample_contents"] = cursor.fetchall()

            # Fetch fields
            cursor.execute("""
                SELECT id, prompt_id, field_path as path, field_key as key, label, field_value as value, field_type as type, is_list, is_primary
                FROM prompt_fields
                WHERE prompt_id = ?
                ORDER BY id ASC
            """, (prompt_id,))
            fields = cursor.fetchall()
            for f in fields:
                f["is_list"] = bool(f.get("is_list", 0))
                f["is_primary"] = bool(f.get("is_primary", 0))
                current_lbl = str(f.get("label") or "").strip()
                if not current_lbl or "." in current_lbl:
                    f["label"] = format_field_label(f.get("key") or f.get("path"), f.get("path"))
            prompt["fields"] = fields

            # Fetch tags
            cursor.execute("""
                SELECT tag
                FROM prompt_tags
                WHERE prompt_id = ?
                ORDER BY id ASC
            """, (prompt_id,))
            prompt["tags"] = [r["tag"] for r in cursor.fetchall()]

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

            # Fetch category
            cursor.execute("SELECT category FROM prompts WHERE id = ?", (prompt_id,))
            p_row = cursor.fetchone()
            cat = p_row["category"] if p_row else "image"

            # Delete old fields and insert new ones
            cursor.execute("DELETE FROM prompt_fields WHERE prompt_id = ?", (prompt_id,))
            new_fields = extract_flat_fields(parsed_json)
            new_fields = detect_primary_fields(new_fields, category=cat)

            for f in new_fields:
                cursor.execute("""
                    INSERT INTO prompt_fields (prompt_id, field_path, field_key, label, field_value, field_type, is_list, is_primary)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    prompt_id,
                    f.get("path", ""),
                    f.get("key", ""),
                    f.get("label", ""),
                    str(f.get("value", "")),
                    f.get("type", "text"),
                    1 if f.get("is_list") else 0,
                    1 if f.get("is_primary") else 0
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
                    # Check if any other prompt still uses this filename
                    cursor.execute("SELECT COUNT(*) as count FROM images WHERE filename = ? AND prompt_id != ?", (fname, prompt_id))
                    ref_count = cursor.fetchone().get("count", 0)
                    if ref_count == 0:
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

            category = parsed_data.get("category", "image")
            if category == "character":
                category = "image"
            note = parsed_data.get("note", "")

            # Insert prompt
            cursor.execute("""
                INSERT INTO prompts (id, original_index, title, raw_title, prompt_type, raw_content, prompt_code, parsed_json, category, note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (new_id, new_idx, title, raw_title, prompt_type, raw_content, prompt_code, parsed_json_str, category, note))

            # Insert images
            import base64
            from app.config import IMAGES_DIR
            IMAGES_DIR.mkdir(parents=True, exist_ok=True)

            for idx, img_item in enumerate(parsed_data.get("images", [])):
                if img_item and isinstance(img_item, str):
                    img_item_clean = img_item.strip()
                    if img_item_clean.startswith("data:image/"):
                        try:
                            header, b64_str = img_item_clean.split(",", 1)
                            ext = "png"
                            if "jpeg" in header or "jpg" in header:
                                ext = "jpg"
                            elif "webp" in header:
                                ext = "webp"
                            elif "gif" in header:
                                ext = "gif"

                            filename = f"{new_id}_upload_{idx + 1}.{ext}"
                            file_path = IMAGES_DIR / filename
                            img_bytes = base64.b64decode(b64_str)
                            with open(file_path, "wb") as f:
                                f.write(img_bytes)

                            local_path = f"images/{filename}"
                            file_size = len(img_bytes)

                            cursor.execute("""
                                INSERT INTO images (prompt_id, url, local_path, filename, status, file_size)
                                VALUES (?, ?, ?, ?, 'downloaded', ?)
                            """, (new_id, local_path, local_path, filename, file_size))
                        except Exception as e:
                            print(f"[!] Error saving uploaded base64 image: {e}")
                    else:
                        filename = f"{new_id}_img_{idx + 1}.jpg"
                        local_path = f"images/{filename}"
                        cursor.execute("""
                            INSERT INTO images (prompt_id, url, local_path, filename, status, file_size)
                            VALUES (?, ?, ?, ?, 'pending', 0)
                        """, (new_id, img_item_clean, local_path, filename))

            # Insert sample content if provided
            sample_content = parsed_data.get("sample_content", "")
            if sample_content and str(sample_content).strip():
                cursor.execute("""
                    INSERT INTO sample_contents (prompt_id, content, title)
                    VALUES (?, ?, ?)
                """, (new_id, str(sample_content).strip(), "Content mẫu #1"))

            # Insert fields
            for idx, f in enumerate(parsed_data.get("fields", [])):
                is_pri = 1 if f.get("is_primary") or idx < 3 else 0
                cursor.execute("""
                    INSERT INTO prompt_fields (prompt_id, field_path, field_key, label, field_value, field_type, is_list, is_primary)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    new_id,
                    f.get("path", ""),
                    f.get("key", ""),
                    f.get("label", ""),
                    str(f.get("value", "")),
                    f.get("type", "text"),
                    1 if f.get("is_list") else 0,
                    is_pri
                ))

            conn.commit()

        return PromptRepository.get_prompt_by_id(new_id)

    @staticmethod
    def update_field_primary(prompt_id: str, field_id: int, is_primary: bool) -> bool:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE prompt_fields 
                SET is_primary = ?
                WHERE id = ? AND prompt_id = ?
            """, (1 if is_primary else 0, field_id, prompt_id))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def suggest_and_apply_primary_fields(prompt_id: str, min_primary: int = 3, max_primary: int = 8) -> Tuple[Optional[Dict[str, Any]], str]:
        from app.services.ai_primary_suggester import call_ai_suggest_primary_fields
        prompt = PromptRepository.get_prompt_by_id(prompt_id)
        if not prompt:
            return None, "Prompt không tồn tại"

        fields = prompt.get("fields") or []
        if not fields:
            return prompt, "Prompt không có trường tham số nào"

        success, updated_fields, msg = call_ai_suggest_primary_fields(prompt, fields)

        with get_db() as conn:
            cursor = conn.cursor()
            for f in updated_fields:
                is_pri = 1 if f.get("is_primary") else 0
                cursor.execute("""
                    UPDATE prompt_fields
                    SET is_primary = ?
                    WHERE id = ? AND prompt_id = ?
                """, (is_pri, f["id"], prompt_id))
            conn.commit()

        return PromptRepository.get_prompt_by_id(prompt_id), msg

    @staticmethod
    def add_sample_content(prompt_id: str, content: str, title: str = "") -> Optional[Dict[str, Any]]:
        clean_content = (content or "").strip()
        if not clean_content:
            return None
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as cnt, COALESCE(MAX(order_index), 0) + 1 as next_order FROM sample_contents WHERE prompt_id = ?", (prompt_id,))
            row = cursor.fetchone()
            cnt = row["cnt"] if row else 0
            next_order = row["next_order"] if row else 1
            sample_title = title.strip() or f"Content mẫu #{cnt + 1}"
            cursor.execute("""
                INSERT INTO sample_contents (prompt_id, content, title, order_index)
                VALUES (?, ?, ?, ?)
            """, (prompt_id, clean_content, sample_title, next_order))
            content_id = cursor.lastrowid
            conn.commit()
            cursor.execute("SELECT id, prompt_id, content, title, order_index, created_at FROM sample_contents WHERE id = ?", (content_id,))
            return cursor.fetchone()

    @staticmethod
    def reorder_sample_contents(prompt_id: str, ordered_ids: List[int]) -> bool:
        if not ordered_ids:
            return True
        with get_db() as conn:
            cursor = conn.cursor()
            for idx, cid in enumerate(ordered_ids):
                cursor.execute("""
                    UPDATE sample_contents
                    SET order_index = ?
                    WHERE id = ? AND prompt_id = ?
                """, (idx, cid, prompt_id))
            conn.commit()
            return True

    @staticmethod
    def delete_sample_content(prompt_id: str, content_id: int) -> bool:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM sample_contents WHERE id = ? AND prompt_id = ?", (content_id, prompt_id))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def update_prompt_note(prompt_id: str, note: str) -> bool:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE prompts SET note = ? WHERE id = ?", ((note or "").strip(), prompt_id))
            conn.commit()
            return cursor.rowcount > 0

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

    @staticmethod
    def add_multiple_images_to_prompt(prompt_id: str, media_items: List[str]) -> List[str]:
        import base64
        from app.config import IMAGES_DIR
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)

        added = []
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as cnt, COALESCE(MAX(order_index), 0) as max_order FROM images WHERE prompt_id = ?", (prompt_id,))
            row = cursor.fetchone()
            current_count = row["cnt"]
            max_order = row["max_order"]

            for idx, img_item in enumerate(media_items):
                if not img_item or not isinstance(img_item, str):
                    continue
                img_item_clean = img_item.strip()
                if not img_item_clean:
                    continue

                item_number = current_count + idx + 1
                new_order = max_order + idx + 1
                if img_item_clean.startswith("data:image/"):
                    try:
                        header, b64_str = img_item_clean.split(",", 1)
                        ext = "png"
                        if "jpeg" in header or "jpg" in header:
                            ext = "jpg"
                        elif "webp" in header:
                            ext = "webp"
                        elif "gif" in header:
                            ext = "gif"

                        filename = f"{prompt_id}_add_{item_number}.{ext}"
                        file_path = IMAGES_DIR / filename
                        img_bytes = base64.b64decode(b64_str)
                        with open(file_path, "wb") as f:
                            f.write(img_bytes)

                        local_path = f"images/{filename}"
                        file_size = len(img_bytes)

                        cursor.execute("""
                            INSERT INTO images (prompt_id, url, local_path, filename, status, file_size, order_index)
                            VALUES (?, ?, ?, ?, 'downloaded', ?, ?)
                        """, (prompt_id, local_path, local_path, filename, file_size, new_order))
                        added.append(filename)
                    except Exception as e:
                        print(f"[!] Error saving added base64 image: {e}")
                else:
                    filename = f"{prompt_id}_add_{item_number}.jpg"
                    local_path = f"images/{filename}"
                    cursor.execute("""
                        INSERT INTO images (prompt_id, url, local_path, filename, status, file_size, order_index)
                        VALUES (?, ?, ?, ?, 'pending', 0, ?)
                    """, (prompt_id, img_item_clean, local_path, filename, new_order))
                    added.append(filename)

            conn.commit()

        return added

    @staticmethod
    def reorder_prompt_images(prompt_id: str, image_ids: List[int]) -> bool:
        with get_db() as conn:
            cursor = conn.cursor()
            for idx, img_id in enumerate(image_ids):
                cursor.execute("""
                    UPDATE images
                    SET order_index = ?
                    WHERE id = ? AND prompt_id = ?
                """, (idx + 1, img_id, prompt_id))
            conn.commit()
            return True

    @staticmethod
    def delete_prompt_image(prompt_id: str, image_id: int) -> bool:
        from app.config import IMAGES_DIR
        filename = None
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT filename FROM images WHERE id = ? AND prompt_id = ?", (image_id, prompt_id))
            row = cursor.fetchone()
            if not row:
                return False
            filename = row.get("filename")
            cursor.execute("DELETE FROM images WHERE id = ? AND prompt_id = ?", (image_id, prompt_id))
            conn.commit()

        # Delete local file if it exists
        if filename:
            try:
                p = IMAGES_DIR / filename
                if p.exists() and p.is_file():
                    p.unlink()
            except Exception as e:
                print(f"[!] Warning deleting image file {filename}: {e}")
        return True

    @staticmethod
    def overwrite_prompt(
        prompt_id: str,
        title: str,
        prompt_code: str,
        raw_content: Optional[str] = None,
        prompt_type: str = "json",
        parsed_json: Optional[Dict[str, Any]] = None,
        fields: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[Dict[str, Any]]:
        from app.services.parser import extract_flat_fields
        with get_db() as conn:
            cursor = conn.cursor()
            parsed_json_str = json.dumps(parsed_json, ensure_ascii=False) if parsed_json else None
            clean_raw = raw_content if raw_content is not None else prompt_code

            cursor.execute("""
                UPDATE prompts
                SET title = ?, prompt_code = ?, raw_content = ?, prompt_type = ?, parsed_json = ?
                WHERE id = ?
            """, (title, prompt_code, clean_raw, prompt_type, parsed_json_str, prompt_id))

            # Delete old fields
            cursor.execute("DELETE FROM prompt_fields WHERE prompt_id = ?", (prompt_id,))

            target_fields = fields
            cursor.execute("SELECT category FROM prompts WHERE id = ?", (prompt_id,))
            p_row = cursor.fetchone()
            cat = p_row["category"] if p_row else "image"

            if target_fields is None and parsed_json:
                target_fields = extract_flat_fields(parsed_json)
                target_fields = detect_primary_fields(target_fields, category=cat)
            elif target_fields is None:
                target_fields = [
                    {"path": "title", "key": "title", "label": "Tiêu đề", "value": title, "type": "text", "is_list": False, "is_primary": True},
                    {"path": "prompt_content", "key": "prompt_content", "label": "Nội dung câu lệnh", "value": prompt_code, "type": "textarea", "is_list": False, "is_primary": True}
                ]
            else:
                target_fields = detect_primary_fields(target_fields, category=cat)

            for f in target_fields:
                cursor.execute("""
                    INSERT INTO prompt_fields (prompt_id, field_path, field_key, label, field_value, field_type, is_list, is_primary)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    prompt_id,
                    f.get("path", ""),
                    f.get("key", ""),
                    f.get("label", ""),
                    str(f.get("value", "")),
                    f.get("type", "text"),
                    1 if f.get("is_list") else 0,
                    1 if f.get("is_primary") else 0
                ))

            conn.commit()

        return PromptRepository.get_prompt_by_id(prompt_id)

    @staticmethod
    def save_as_new_version(
        parent_prompt_id: str,
        title: str,
        prompt_code: str,
        raw_content: Optional[str] = None,
        prompt_type: str = "json",
        parsed_json: Optional[Dict[str, Any]] = None,
        fields: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[Dict[str, Any]]:
        from app.services.parser import extract_flat_fields
        with get_db() as conn:
            cursor = conn.cursor()

            # Find max index and count
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

            parsed_json_str = json.dumps(parsed_json, ensure_ascii=False) if parsed_json else None
            clean_raw = raw_content if raw_content is not None else prompt_code

            # Inherit category and note from parent
            parent_cat = "image"
            parent_note = ""
            if parent_prompt_id:
                cursor.execute("SELECT category, note FROM prompts WHERE id = ?", (parent_prompt_id,))
                p_info = cursor.fetchone()
                if p_info:
                    parent_cat = p_info.get("category") or "image"
                    parent_note = p_info.get("note") or ""

            # Insert new prompt record
            cursor.execute("""
                INSERT INTO prompts (id, original_index, title, raw_title, prompt_type, raw_content, prompt_code, parsed_json, category, note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (new_id, new_idx, title, title, prompt_type, clean_raw, prompt_code, parsed_json_str, parent_cat, parent_note))

            # Copy parent images references so new version retains samples
            if parent_prompt_id:
                cursor.execute("""
                    SELECT url, local_path, filename, status, file_size
                    FROM images
                    WHERE prompt_id = ?
                    ORDER BY id ASC
                """, (parent_prompt_id,))
                parent_images = cursor.fetchall()
                for img in parent_images:
                    cursor.execute("""
                        INSERT INTO images (prompt_id, url, local_path, filename, status, file_size)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (new_id, img["url"], img["local_path"], img["filename"], img["status"], img["file_size"]))

            # Insert fields
            target_fields = fields
            cursor.execute("SELECT category FROM prompts WHERE id = ?", (new_id,))
            p_row = cursor.fetchone()
            cat = p_row["category"] if p_row else parent_cat

            if target_fields is None and parsed_json:
                target_fields = extract_flat_fields(parsed_json)
                target_fields = detect_primary_fields(target_fields, category=cat)
            elif target_fields is None:
                target_fields = [
                    {"path": "title", "key": "title", "label": "Tiêu đề", "value": title, "type": "text", "is_list": False, "is_primary": True},
                    {"path": "prompt_content", "key": "prompt_content", "label": "Nội dung câu lệnh", "value": prompt_code, "type": "textarea", "is_list": False, "is_primary": True}
                ]
            else:
                target_fields = detect_primary_fields(target_fields, category=cat)

            for f in target_fields:
                cursor.execute("""
                    INSERT INTO prompt_fields (prompt_id, field_path, field_key, label, field_value, field_type, is_list, is_primary)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    new_id,
                    f.get("path", ""),
                    f.get("key", ""),
                    f.get("label", ""),
                    str(f.get("value", "")),
                    f.get("type", "text"),
                    1 if f.get("is_list") else 0,
                    1 if f.get("is_primary") else 0
                ))

            conn.commit()

        return PromptRepository.get_prompt_by_id(new_id)

    @staticmethod
    def get_tags(query: Optional[str] = None, limit: int = 25) -> List[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            if query and query.strip():
                clean_q = query.strip().lstrip('#').strip().lower()
                cursor.execute("""
                    SELECT tag, COUNT(*) as count
                    FROM prompt_tags
                    WHERE LOWER(tag) LIKE ?
                    GROUP BY tag
                    ORDER BY count DESC, tag ASC
                    LIMIT ?
                """, (f"%{clean_q}%", limit))
            else:
                cursor.execute("""
                    SELECT tag, COUNT(*) as count
                    FROM prompt_tags
                    GROUP BY tag
                    ORDER BY count DESC, tag ASC
                    LIMIT ?
                """, (limit,))
            return cursor.fetchall()

    @staticmethod
    def get_prompt_tags(prompt_id: str) -> List[str]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT tag
                FROM prompt_tags
                WHERE prompt_id = ?
                ORDER BY id ASC
            """, (prompt_id,))
            return [r["tag"] for r in cursor.fetchall()]

    @staticmethod
    def add_tag_to_prompt(prompt_id: str, tag: str) -> List[str]:
        clean_tag = (tag or "").strip().lstrip('#').strip()
        if not clean_tag or len(clean_tag) > 50:
            return PromptRepository.get_prompt_tags(prompt_id)

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO prompt_tags (prompt_id, tag)
                VALUES (?, ?)
            """, (prompt_id, clean_tag))
            conn.commit()

        return PromptRepository.get_prompt_tags(prompt_id)

    @staticmethod
    def remove_tag_from_prompt(prompt_id: str, tag: str) -> List[str]:
        clean_tag = (tag or "").strip().lstrip('#').strip()
        if not clean_tag:
            return PromptRepository.get_prompt_tags(prompt_id)

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM prompt_tags
                WHERE prompt_id = ? AND LOWER(tag) = LOWER(?)
            """, (prompt_id, clean_tag))
            conn.commit()

        return PromptRepository.get_prompt_tags(prompt_id)


