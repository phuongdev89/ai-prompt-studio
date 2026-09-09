import json
import re
import ssl
import urllib.request
import urllib.error
from typing import List, Dict, Any, Tuple, Optional
from app.config import get_ai_config
from app.db.database import get_db
from app.services.ai_converter import clean_json_response, parse_chat_response

SYSTEM_PROMPT_ASSISTANT = """Bạn là CÔNG CỤ TÌM KIẾM & XẾP HẠNG PROMPT (AI Prompt Search Engine) của nền tảng AI Prompt Studio.
BẠN CÓ MỘT MỤC ĐÍCH DUY NHẤT: LUÔN LUÔN TRẢ VỀ KẾT QUẢ TÌM KIẾM CÁC CÂU LỆNH PROMPT PHÙ HỢP NHẤT TỪ CƠ SỞ DỮ LIỆU.

### NGUYÊN TẮC BẮT BUỘC (TUÂN THỦ 100%):
1. **LUÔN LUÔN TRẢ VỀ KẾT QUẢ TÌM KIẾM PROMPT (MẢNG recommended_prompts)**:
   - Trong BẤT KỲ trường hợp nào, với BẤT KỲ tin nhắn nào của người dùng (kể cả chào hỏi, câu hỏi ngắn, câu hỏi tiếp nối hay mô tả chi tiết), bạn BẮT BUỘC PHẢI LUÔN LUÔN tìm kiếm và trả về từ 1 đến 4 prompt phù hợp nhất trong mảng `recommended_prompts`.
   - TUYỆT ĐỐI KHÔNG BAO GIỜ chỉ trả lời hội thoại suông mà không có danh sách prompt.
   - KHÔNG tán gẫu ngoài lề, KHÔNG giải thích lý thuyết chung chung nếu không đi kèm kết quả prompt cụ thể. Mọi phản hồi đều là kết quả tìm kiếm câu lệnh.
2. **CHỈ SỬ DỤNG ID CÓ TRONG DANH SÁCH ỨNG VIÊN CUNG CẤP**:
   - Chỉ được dùng đúng các `id` từ danh sách ứng viên bên dưới. Tuyệt đối không tự bịa ID.
3. **CHẤM ĐIỂM ĐỘ PHÙ HỢP CHÍNH XÁC (match_score: từ 1 đến 100)**:
   - Từ 90% - 99%: Rất phù hợp, đáp ứng gần như tuyệt đối nhu cầu.
   - Từ 75% - 89%: Phù hợp tốt, chỉnh sửa nhẹ vài thông số là dùng được ngay.
   - Dưới 75%: Tham khảo hoặc đáp ứng một phần.
4. **LÝ DO RÕ RÀNG (reason)**:
   - Nêu ngắn gọn, sắc bén lý do vì sao prompt này giải quyết đúng mục đích của người dùng.
5. **GỢI Ý TÙY CHỈNH CỤ THỂ (recommended_adjustments)**:
   - Chỉ rõ người dùng nên vào prompt và chỉnh sửa hoặc thay thế thông số/thuộc tính nào (ví dụ: đổi bối cảnh, đổi tone giọng, đổi ánh sáng, góc máy,...) để đạt 100% ý muốn.
6. **LỜI DẪN NGẮN GỌN (assistant_reply)**:
   - Tóm tắt kết quả tìm kiếm thật ngắn gọn, súc tích (1-2 câu). Không nói dông dài.

### ĐỊNH DẠNG ĐẦU RA BẮT BUỘC (DUY NHẤT 1 JSON OBJECT):
{
  "assistant_reply": "Tóm tắt kết quả tìm kiếm cho [mục đích của bạn]...",
  "recommended_prompts": [
    {
      "id": "ID_chính_xác_trong_danh_sách",
      "match_score": 95,
      "reason": "Lý do ngắn gọn vì sao prompt này phù hợp...",
      "recommended_adjustments": "Gợi ý thông số cụ thể nên sửa..."
    }
  ],
  "suggested_questions": [
    "Câu hỏi tìm kiếm gợi ý 1...",
    "Câu hỏi tìm kiếm gợi ý 2..."
  ]
}
"""

def extract_search_tokens(text: str) -> List[str]:
    """Trích xuất các từ khóa có nghĩa từ câu hỏi của người dùng."""
    if not text:
        return []
    cleaned = re.sub(r'[^\w\s]', ' ', text.lower())
    words = [w.strip() for w in cleaned.split() if len(w.strip()) >= 2]
    stop_words = {
        "tôi", "muốn", "cần", "tìm", "kiếm", "cho", "cái", "nào", "dùng", "được",
        "không", "này", "đó", "làm", "sao", "giúp", "với", "nhé", "có", "hay",
        "một", "những", "các", "để", "tạo", "ra", "viết", "thì", "prompt", "câu", "lệnh"
    }
    filtered = [w for w in words if w not in stop_words]
    return filtered if filtered else words

def get_candidate_prompts(query: str, category_filter: str = "all", limit: int = 35) -> List[Dict[str, Any]]:
    """
    Truy vấn và xếp hạng sơ bộ các ứng viên prompt từ SQLite dựa trên mức độ liên quan.
    """
    cat = category_filter.lower().strip() if category_filter else "all"
    if cat == "character":
        cat = "image"

    # Tự động đoán category nếu category_filter là 'all'
    inferred_cat = None
    if cat == "all" and query:
        q_lower = query.lower()
        image_keywords = ["ảnh", "chụp", "portrait", "chân dung", "storyboard", "pose", "khung hình", "12 ô", "outfit", "nhiếp ảnh", "camera", "mặt", "gương mặt", "váy", "áo dài", "vintage", "retro", "cosplay", "lighting", "điện ảnh"]
        content_keywords = ["kịch bản", "bài viết", "content", "tiktok", "reels", "shorts", "seo", "blog", "livestream", "affiliate", "review", "chốt đơn", "lời thoại", "koc", "bán hàng", "quảng cáo"]
        
        has_img = any(k in q_lower for k in image_keywords)
        has_cnt = any(k in q_lower for k in content_keywords)
        if has_img and not has_cnt:
            inferred_cat = "image"
        elif has_cnt and not has_img:
            inferred_cat = "content"

    target_cat = cat if cat in ("image", "content") else inferred_cat

    with get_db() as conn:
        cursor = conn.cursor()

        # Lấy danh sách prompt cơ bản
        sql = """
            SELECT p.id, p.title, p.category, p.note, p.prompt_type, p.raw_content,
                   (SELECT COUNT(*) FROM images img WHERE img.prompt_id = p.id) as image_count,
                   (SELECT COUNT(*) FROM sample_contents sc WHERE sc.prompt_id = p.id) as sample_count
            FROM prompts p
        """
        params = []
        if target_cat:
            sql += " WHERE p.category = ?"
            params.append(target_cat)
        sql += " ORDER BY p.original_index ASC"

        cursor.execute(sql, params)
        prompts = cursor.fetchall()

        if not prompts and target_cat:
            cursor.execute("""
                SELECT p.id, p.title, p.category, p.note, p.prompt_type, p.raw_content,
                       (SELECT COUNT(*) FROM images img WHERE img.prompt_id = p.id) as image_count,
                       (SELECT COUNT(*) FROM sample_contents sc WHERE sc.prompt_id = p.id) as sample_count
                FROM prompts p
                ORDER BY p.original_index ASC
            """)
            prompts = cursor.fetchall()

        # Lấy tags cho tất cả prompt
        cursor.execute("SELECT prompt_id, tag FROM prompt_tags")
        tags_rows = cursor.fetchall()
        tags_map = {}
        for r in tags_rows:
            tags_map.setdefault(r["prompt_id"], []).append(r["tag"])

        # Lấy primary fields cho tất cả prompt
        cursor.execute("""
            SELECT prompt_id, field_key, label, field_value 
            FROM prompt_fields 
            WHERE is_primary = 1
        """)
        field_rows = cursor.fetchall()
        fields_map = {}
        for r in field_rows:
            label = r["label"] or r["field_key"]
            val = (r["field_value"] or "").strip()
            if val and len(val) < 80:
                fields_map.setdefault(r["prompt_id"], []).append(f"{label}: {val}")

    tokens = extract_search_tokens(query)

    scored_prompts = []
    for p in prompts:
        pid = p["id"]
        title = p["title"] or ""
        note = p["note"] or ""
        content = p["raw_content"] or ""
        tags = tags_map.get(pid, [])
        primary_fields = fields_map.get(pid, [])

        score = 0
        if tokens:
            title_l = title.lower()
            note_l = note.lower()
            tags_l = [t.lower() for t in tags]
            content_l = content.lower()

            for t in tokens:
                if t in title_l:
                    score += 15
                if any(t in tag for tag in tags_l):
                    score += 12
                if t in note_l:
                    score += 8
                if any(t in pf.lower() for pf in primary_fields):
                    score += 6
                if t in content_l:
                    score += 2

            q_clean = query.lower().strip()
            if len(q_clean) > 3 and q_clean in title_l:
                score += 30
            if len(q_clean) > 3 and q_clean in note_l:
                score += 20

        scored_prompts.append({
            "score": score,
            "id": pid,
            "title": title,
            "category": p["category"],
            "note": note[:150] if note else "",
            "tags": tags[:5],
            "highlights": "; ".join(primary_fields[:4]) if primary_fields else "",
            "image_count": p["image_count"],
            "sample_count": p["sample_count"]
        })

    # Sắp xếp theo điểm giảm dần
    scored_prompts.sort(key=lambda x: x["score"], reverse=True)

    candidates = scored_prompts[:limit]
    return candidates

def enrich_recommended_prompts(recs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Bổ sung metadata đầy đủ (ảnh đại diện, tags, prompt code) từ SQLite cho các prompt được gợi ý."""
    if not recs:
        return []

    prompt_ids = [r.get("id") for r in recs if r.get("id")]
    if not prompt_ids:
        return []

    with get_db() as conn:
        cursor = conn.cursor()
        placeholders = ",".join("?" for _ in prompt_ids)
        cursor.execute(f"""
            SELECT p.id, p.title, p.category, p.note, p.prompt_code, p.raw_content,
                   (SELECT COUNT(*) FROM images img WHERE img.prompt_id = p.id) as image_count,
                   (SELECT COUNT(*) FROM sample_contents sc WHERE sc.prompt_id = p.id) as sample_count
            FROM prompts p
            WHERE p.id IN ({placeholders})
        """, prompt_ids)
        db_prompts = {row["id"]: row for row in cursor.fetchall()}

        cursor.execute(f"""
            SELECT prompt_id, url, local_path, filename
            FROM images
            WHERE prompt_id IN ({placeholders})
            ORDER BY order_index ASC, id ASC
        """, prompt_ids)
        img_rows = cursor.fetchall()
        img_map = {}
        for r in img_rows:
            if r["prompt_id"] not in img_map:
                img_path = ""
                if r.get("local_path") and r.get("filename"):
                    img_path = f"/data/images/{r['filename']}"
                elif r.get("url"):
                    img_path = r["url"]
                img_map[r["prompt_id"]] = img_path

        cursor.execute(f"""
            SELECT prompt_id, tag
            FROM prompt_tags
            WHERE prompt_id IN ({placeholders})
            ORDER BY id ASC
        """, prompt_ids)
        tag_rows = cursor.fetchall()
        tags_map = {}
        for r in tag_rows:
            tags_map.setdefault(r["prompt_id"], []).append(r["tag"])

    enriched = []
    for r in recs:
        pid = r.get("id")
        if pid not in db_prompts:
            continue
        p = db_prompts[pid]
        
        score_val = r.get("match_score", 90)
        try:
            score_val = int(score_val)
            score_val = max(1, min(100, score_val))
        except Exception:
            score_val = 90

        enriched.append({
            "id": pid,
            "title": p["title"] or r.get("title", pid),
            "category": p["category"] or r.get("category", "image"),
            "match_score": score_val,
            "reason": r.get("reason", "Prompt này phù hợp với nhu cầu của bạn."),
            "recommended_adjustments": r.get("recommended_adjustments", "Bạn có thể dùng ngay hoặc chỉnh sửa các thuộc tính cho phù hợp."),
            "thumbnail": img_map.get(pid, ""),
            "image_count": p["image_count"],
            "sample_count": p["sample_count"],
            "tags": tags_map.get(pid, [])[:4],
            "note": p["note"] or "",
            "prompt_code": p["prompt_code"] or p["raw_content"] or ""
        })

    return enriched

def call_ai_search_assistant(
    message: str,
    history: Optional[List[Dict[str, Any]]] = None,
    category_filter: str = "all",
    provider: Optional[str] = None
) -> Tuple[bool, Dict[str, Any], str]:
    """
    Thực hiện gọi AI Assistant để tìm kiếm, phân tích và gợi ý prompt.
    Trả về (success, result_dict, message_log).
    """
    if not message or not message.strip():
        return False, {}, "Tin nhắn không được để trống."

    user_query = message.strip()
    cfg = get_ai_config()
    active_provider = (provider or cfg.get("provider") or "openai").lower()

    # Xây dựng ngữ cảnh tìm kiếm từ lịch sử nếu người dùng tiếp tục chat
    search_context_query = user_query
    if history and isinstance(history, list):
        past_user_terms = [
            str(h.get("content", "")) for h in history
            if isinstance(h, dict) and h.get("role") == "user" and isinstance(h.get("content"), (str, int))
        ]
        if past_user_terms:
            # Gộp tối đa 2 câu hỏi gần nhất của user để giữ bối cảnh tìm kiếm
            search_context_query = f"{' '.join(past_user_terms[-2:])} {user_query}".strip()

    # 1. Trích xuất danh sách ứng viên từ SQLite
    candidates = get_candidate_prompts(search_context_query, category_filter=category_filter, limit=35)
    if not candidates and search_context_query != user_query:
        candidates = get_candidate_prompts(user_query, category_filter=category_filter, limit=35)
    
    # 2. Xây dựng Candidate Context gọn nhẹ
    candidate_summary = []
    for c in candidates:
        info = f"ID: {c['id']} | Tiêu đề: {c['title']} | Loại: {c['category']}"
        if c.get("tags"):
            info += f" | Tags: {', '.join(c['tags'])}"
        if c.get("note"):
            info += f" | Ghi chú: {c['note']}"
        if c.get("highlights"):
            info += f" | Thuộc tính chính: {c['highlights']}"
        candidate_summary.append(info)

    candidate_text = "\n".join(candidate_summary)

    # 3. Tạo User Content kết hợp ngữ cảnh
    formatted_user_prompt = f"""--- CÂU LỆNH ỨNG VIÊN CÓ TRONG HỆ THỐNG ({len(candidates)} prompt) ---
{candidate_text}

--- BỘ LỌC DANH MỤC HIỆN TẠI ---
{category_filter}

--- Ý TƯỞNG / YÊU CẦU TÌM KIẾM CỦA NGƯỜI DÙNG ---
{user_query}

LƯU Ý QUAN TRỌNG: Bạn là công cụ tìm kiếm prompt. Bạn PHẢI LUÔN LUÔN trả về mảng `recommended_prompts` chứa 1 đến 4 prompt phù hợp nhất từ danh sách ứng viên (CHỈ dùng ID có trong danh sách). Tuyệt đối không chỉ trả lời văn bản mà không có danh sách prompt. Trả về đúng JSON theo cấu trúc."""

    # 4. Gửi yêu cầu tới Provider AI
    if active_provider == "gemini":
        success, raw_result, msg = _call_gemini_assistant(formatted_user_prompt, history, cfg)
    else:
        success, raw_result, msg = _call_openai_assistant(formatted_user_prompt, history, cfg)

    if not success:
        return False, {}, msg

    if not isinstance(raw_result, dict):
        return False, {}, "Kết quả trả về từ AI không đúng cấu trúc JSON."

    # 5. Enrich kết quả với dữ liệu thật trong SQLite
    raw_recs = raw_result.get("recommended_prompts", [])
    if not isinstance(raw_recs, list):
        raw_recs = []

    enriched_recs = enrich_recommended_prompts(raw_recs)

    # BẢO ĐẢM LUÔN LUÔN CÓ KẾT QUẢ TÌM KIẾM (Guaranteed Search Results)
    # Nếu AI không chọn được ID hoặc trả về rỗng, lập tức lấy các ứng viên điểm cao nhất từ SQLite
    if not enriched_recs and candidates:
        top_cands = candidates[:3]
        fallback_recs = []
        for tc in top_cands:
            fallback_recs.append({
                "id": tc["id"],
                "match_score": max(75, min(95, 80 + int(tc.get("score", 0)))),
                "reason": f"Câu lệnh phù hợp nhất trong cơ sở dữ liệu cho yêu cầu: '{user_query}'.",
                "recommended_adjustments": "Bạn có thể vào xem chi tiết để tùy chỉnh các thông số theo đúng nhu cầu."
            })
        enriched_recs = enrich_recommended_prompts(fallback_recs)

    final_reply = raw_result.get("assistant_reply") or f"Kết quả tìm kiếm phù hợp nhất cho '{user_query}':"
    follow_ups = raw_result.get("suggested_questions") or [
        "Cần tinh chỉnh thêm thông số nào không?",
        "Tìm kiếm thêm các phong cách tương tự?"
    ]
    if not isinstance(follow_ups, list):
        follow_ups = []

    result = {
        "assistant_reply": final_reply,
        "recommendations": enriched_recs,
        "suggested_questions": follow_ups[:3],
        "category_filter": category_filter,
        "total_candidates_analyzed": len(candidates)
    }

    return True, result, "Tìm kiếm prompt thành công"

def _call_gemini_assistant(
    user_prompt: str,
    history: Optional[List[Dict[str, Any]]],
    cfg: Dict[str, Any]
) -> Tuple[bool, Any, str]:
    """Gọi Google Gemini API trực tiếp với chuẩn hóa history."""
    api_key = cfg.get("gemini_api_key", "").strip()
    model_name = cfg.get("gemini_chat_model", "gemini-2.0-flash") or "gemini-2.0-flash"
    timeout = cfg.get("timeout", 90)

    if not api_key:
        return False, None, "Chưa cấu hình GEMINI_API_KEY trong tệp .env."

    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

    # Build contents with strictly alternating roles for Gemini
    contents = []
    if history and isinstance(history, list):
        last_role = None
        for h in history[-6:]:
            if not isinstance(h, dict):
                continue
            role = "user" if h.get("role") == "user" else "model"
            text = h.get("content")
            if not isinstance(text, str):
                text = str(text or "")
            text = text.strip()
            if text:
                if role == last_role:
                    contents[-1]["parts"][0]["text"] += f"\n{text}"
                else:
                    contents.append({"role": role, "parts": [{"text": text}]})
                    last_role = role

        # If last history message was 'user', merge it into user_prompt to avoid double user messages
        if contents and contents[-1]["role"] == "user":
            popped_text = contents.pop()["parts"][0]["text"]
            user_prompt = f"[Câu hỏi trước: {popped_text}]\n\n{user_prompt}"

    contents.append({"role": "user", "parts": [{"text": user_prompt}]})

    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT_ASSISTANT}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json"
        }
    }

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
            candidates = data.get("candidates", [])
            if not candidates:
                return False, None, "Gemini không trả về nội dung nào."
            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                return False, None, "Gemini trả về nội dung rỗng."
            text_out = parts[0].get("text", "").strip()

            cleaned = clean_json_response(text_out)
            parsed = json.loads(cleaned)
            return True, parsed, "Thành công từ Gemini"
    except Exception as e:
        return False, None, f"Lỗi Gemini Assistant: {str(e)}"

def _call_openai_assistant(
    user_prompt: str,
    history: Optional[List[Dict[str, Any]]],
    cfg: Dict[str, Any]
) -> Tuple[bool, Any, str]:
    """Gọi OpenAI / Custom Gateway (9router / OpenRouter / DeepSeek / Ollama) với chuẩn hóa history."""
    api_key = cfg.get("api_key", "").strip()
    base_url = cfg.get("base_url", "https://api.openai.com/v1").strip()
    model_name = cfg.get("chat_model") or cfg.get("model_name") or "gpt-4o-mini"
    timeout = cfg.get("timeout", 90)

    if not api_key:
        return False, None, "Chưa cấu hình AI_API_KEY trong tệp .env."

    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    messages = [{"role": "system", "content": SYSTEM_PROMPT_ASSISTANT}]
    if history and isinstance(history, list):
        for h in history[-6:]:
            if not isinstance(h, dict):
                continue
            role = "user" if h.get("role") == "user" else "assistant"
            text = h.get("content")
            if not isinstance(text, str):
                text = str(text or "")
            text = text.strip()
            if text:
                messages.append({"role": role, "content": text})

    messages.append({"role": "user", "content": user_prompt})

    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": 0.2,
        "stream": False
    }

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers
        )
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            body_text = resp.read().decode("utf-8", errors="ignore")
            content = parse_chat_response(body_text)
            if not content:
                return False, None, "Phản hồi AI trống."

            cleaned = clean_json_response(content)
            parsed = json.loads(cleaned)
            return True, parsed, "Thành công từ OpenAI Provider"
    except Exception as e:
        return False, None, f"Lỗi AI Assistant: {str(e)}"
