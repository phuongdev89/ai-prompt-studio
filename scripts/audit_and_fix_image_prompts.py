import sqlite3
import json
import re
from pathlib import Path
from app.services.ai_converter import normalize_reference_image_in_json, sanitize_text_reference_images
from app.db.repository import PromptRepository

def audit_and_fix_image_prompts():
    conn = sqlite3.connect("data/prompts.db", timeout=30.0)
    c = conn.cursor()
    c.execute("""
        SELECT id, title, prompt_type, requires_reference, prompt_code, parsed_json, raw_content, compact_prompt
        FROM prompts
        WHERE category = 'image'
        ORDER BY original_index ASC
    """)
    rows = c.fetchall()
    conn.close()

    print(f"Total image prompts to audit: {len(rows)}")

    fixed_json_count = 0
    fixed_json_raw_count = 0
    fixed_compact_count = 0
    fixed_requires_ref_count = 0

    ref_kw_re = re.compile(r'(?i)(ảnh\s*(?:tham\s*chiếu|mẫu|gốc|đính\s*kèm)|reference\s*image|ATTACHED_PHOTO|--cref|identity_lock|primary_subject_reference|consistent_character|koc|chân\s*dung|khuôn\s*mặt|ngũ\s*quan)')

    extra_sql_updates = []

    for r in rows:
        pid, title, ptype, req_ref, pcode, pjson_str, raw_c, compact_p = r
        pcode = pcode or ""
        
        # Check requires_reference
        should_require_ref = req_ref
        if req_ref == 0:
            if ref_kw_re.search(pcode) or ref_kw_re.search(title) or ref_kw_re.search(raw_c or ""):
                should_require_ref = 1
                extra_sql_updates.append(("UPDATE prompts SET requires_reference = 1 WHERE id = ?", (pid,)))
                fixed_requires_ref_count += 1

        # Check if json_raw can be parsed into parsed_json
        if ptype == "json_raw" and pcode.strip().startswith("{") and (not pjson_str or pjson_str.strip() == ""):
            try:
                parsed = json.loads(pcode.strip())
                norm_pj, has_ref = normalize_reference_image_in_json(parsed, pcode)
                new_pcode = json.dumps(norm_pj, ensure_ascii=False, indent=2)
                PromptRepository.update_prompt_json_structure(
                    prompt_id=pid,
                    parsed_json=norm_pj,
                    prompt_code=new_pcode,
                    requires_reference=True if (should_require_ref or has_ref) else None
                )
                fixed_json_raw_count += 1
                continue
            except Exception as e:
                print(f"Error parsing json_raw for {pid}: {e}")

        # Check standard JSON prompts
        if pjson_str and pjson_str.strip():
            try:
                pj = json.loads(pjson_str)
                norm_pj, has_ref = normalize_reference_image_in_json(pj, pcode)
                new_serialized = json.dumps(norm_pj, ensure_ascii=False)
                new_pcode = json.dumps(norm_pj, ensure_ascii=False, indent=2)
                
                # Check if changes were made
                if new_serialized != pjson_str or new_pcode != pcode:
                    PromptRepository.update_prompt_json_structure(
                        prompt_id=pid,
                        parsed_json=norm_pj,
                        prompt_code=new_pcode,
                        requires_reference=True if (should_require_ref or has_ref) else None
                    )
                    fixed_json_count += 1
            except Exception as e:
                print(f"Error processing {pid}: {e}")

        # Check compact_prompt
        if compact_p and compact_p.strip():
            cp_clean = compact_p.strip()
            if should_require_ref and "[ATTACHED_PHOTO]" not in cp_clean and "--cref" not in cp_clean:
                # Add reference requirement to compact prompt
                if "--ar" in cp_clean or "midjourney" in cp_clean.lower():
                    new_cp = f"{cp_clean} --cref [ATTACHED_PHOTO]"
                else:
                    new_cp = f"{cp_clean} Reference: Strict consistency matching [ATTACHED_PHOTO]."
                if len(new_cp) <= 1000:
                    extra_sql_updates.append(("UPDATE prompts SET compact_prompt = ? WHERE id = ?", (new_cp, pid)))
                    fixed_compact_count += 1

    # Execute extra SQL updates
    conn = sqlite3.connect("data/prompts.db", timeout=30.0)
    c = conn.cursor()
    for sql, params in extra_sql_updates:
        c.execute(sql, params)

    # Clean prompt_fields for any remaining image filenames or old labels
    c.execute("""
        UPDATE prompt_fields
        SET field_value = '[ATTACHED_PHOTO]'
        WHERE field_value LIKE '%image_0.png%' 
           OR field_value LIKE '%image_0%'
           OR field_value LIKE 'Ảnh tham chiếu tải lên'
           OR (field_key IN ('primary_subject_reference', 'reference_image', 'identity_reference', 'outfit_reference') 
               AND (field_value LIKE '%.png' OR field_value LIKE '%.jpg' OR field_value = 'null' OR field_value = ''))
    """)

    conn.commit()
    conn.close()

    print(f"Audit & repair completed successfully:")
    print(f"- Updated requires_reference: {fixed_requires_ref_count}")
    print(f"- Converted json_raw to structured JSON: {fixed_json_raw_count}")
    print(f"- Standardized JSON prompts with [ATTACHED_PHOTO] and directives: {fixed_json_count}")
    print(f"- Fixed compact prompts missing reference directive: {fixed_compact_count}")

if __name__ == "__main__":
    audit_and_fix_image_prompts()
