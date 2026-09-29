import sqlite3
import json
import re
from app.services.ai_compact_generator import (
    is_reference_required,
    ensure_reference_in_compact_prompt,
    sanitize_compact_reference_tokens
)

def run_audit():
    conn = sqlite3.connect("data/prompts.db", timeout=30.0)
    cursor = conn.cursor()

    # 1. Fetch all prompts
    cursor.execute("""
        SELECT id, title, category, requires_reference, prompt_code, raw_content, original_raw_content, compact_prompt
        FROM prompts
        ORDER BY original_index ASC
    """)
    rows = cursor.fetchall()

    print(f"Total prompts in DB: {len(rows)}")

    fixed_image_requires_ref = 0
    fixed_compact_ref = 0
    fixed_compact_sanitize = 0

    updates = []

    for r in rows:
        pid, title, cat, req_ref, pcode, raw_c, orig_raw, compact_p = r

        # Check if category is image but requires_reference is not 1
        if cat == "image" and req_ref != 1:
            cursor.execute("UPDATE prompts SET requires_reference = 1 WHERE id = ?", (pid,))
            fixed_image_requires_ref += 1
            req_ref = 1

        prompt_dict = {
            "id": pid,
            "title": title,
            "category": cat,
            "requires_reference": req_ref,
            "prompt_code": pcode,
            "raw_content": raw_c,
            "original_raw_content": orig_raw
        }

        should_req_ref = is_reference_required(prompt_dict)

        if compact_p and compact_p.strip():
            cp_orig = compact_p.strip()
            cp_sanitized = sanitize_compact_reference_tokens(cp_orig)
            if cp_sanitized != cp_orig:
                fixed_compact_sanitize += 1

            if should_req_ref:
                cp_final = ensure_reference_in_compact_prompt(cp_sanitized, requires_reference=True)
            else:
                cp_final = cp_sanitized

            if cp_final != cp_orig:
                updates.append((cp_final, pid))
                fixed_compact_ref += 1

    for new_cp, pid in updates:
        cursor.execute("UPDATE prompts SET compact_prompt = ? WHERE id = ?", (new_cp, pid))

    conn.commit()
    conn.close()

    print(f"Audited successfully:")
    print(f"- Image prompts updated with requires_reference=1: {fixed_image_requires_ref}")
    print(f"- Compact prompts sanitized (filenames/placeholders): {fixed_compact_sanitize}")
    print(f"- Compact prompts updated with [ATTACHED_PHOTO]: {fixed_compact_ref}")

if __name__ == "__main__":
    run_audit()
