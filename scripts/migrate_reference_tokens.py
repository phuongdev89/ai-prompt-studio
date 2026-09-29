import sqlite3
import json
from pathlib import Path
from app.services.ai_converter import normalize_reference_image_in_json, sanitize_text_reference_images
from app.db.repository import PromptRepository

def migrate_database():
    db_path = Path("data/prompts.db")
    if not db_path.exists():
        print("Database not found:", db_path)
        return

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT id, prompt_type, prompt_code, parsed_json, raw_content FROM prompts")
    rows = c.fetchall()

    updated_count = 0
    for pid, ptype, pcode, pjson_str, raw_c in rows:
        needs_update = False
        new_pcode = pcode
        new_pjson = None
        has_reference_flag = False

        if pjson_str:
            try:
                pj = json.loads(pjson_str)
                norm_pj, has_ref = normalize_reference_image_in_json(pj, pcode or "")
                serialized = json.dumps(norm_pj, ensure_ascii=False)
                if serialized != pjson_str or (pcode and ("image_0" in pcode or "Ảnh tham chiếu" in pcode)):
                    needs_update = True
                    new_pjson = norm_pj
                    new_pcode = json.dumps(norm_pj, ensure_ascii=False, indent=2)
                    has_reference_flag = has_ref
            except Exception as e:
                print(f"Error parsing JSON for {pid}: {e}")

        if not needs_update and pcode and ("image_0" in pcode or ".png" in pcode or ".jpg" in pcode or "Ảnh tham chiếu" in pcode):
            cleaned = sanitize_text_reference_images(pcode)
            if cleaned != pcode:
                needs_update = True
                new_pcode = cleaned

        if needs_update:
            if new_pjson:
                PromptRepository.update_prompt_json_structure(
                    prompt_id=pid,
                    parsed_json=new_pjson,
                    prompt_code=new_pcode,
                    requires_reference=True if has_reference_flag else None
                )
            else:
                c.execute("UPDATE prompts SET prompt_code = ? WHERE id = ?", (new_pcode, pid))
                conn.commit()
            updated_count += 1

    # Also clean prompt_fields table
    c.execute("""
        UPDATE prompt_fields
        SET field_value = '[ATTACHED_PHOTO]'
        WHERE field_value LIKE '%image_0.png%' 
           OR field_value LIKE '%image_0%'
           OR field_value LIKE 'Ảnh tham chiếu tải lên'
           OR (field_key IN ('primary_subject_reference', 'reference_image') AND (field_value LIKE '%.png' OR field_value LIKE '%.jpg'))
    """)
    conn.commit()
    conn.close()

    print(f"Migration completed successfully. Updated {updated_count} prompts in prompts.db.")

if __name__ == "__main__":
    migrate_database()
