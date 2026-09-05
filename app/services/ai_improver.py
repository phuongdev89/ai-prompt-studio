import json
import re
import ssl
import urllib.request
import urllib.error
from typing import Dict, Any, Tuple, Optional, List
from app.config import get_ai_config
from app.services.parser import extract_flat_fields
from app.services.ai_converter import clean_json_response, parse_chat_response

# =====================================================================
# Strict Schema Preservation & Reconciliation Helpers
# =====================================================================

def preserve_and_reconcile_schema(original: Any, improved: Any) -> Any:
    """
    Bảo toàn nghiêm ngặt 100% các thuộc tính, trường và thứ tự xuất hiện từ prompt gốc.
    - Không xóa bất kỳ thuộc tính nào từ `original`.
    - Giữ nguyên vị trí và thứ tự của các key theo đúng thứ tự của `original`.
    - Cập nhật giá trị đã cải tiến từ `improved` vào các trường tương ứng.
    - Bất kỳ trường nào AI bỏ quên hoặc làm thiếu sẽ được phục hồi nguyên vẹn từ `original`.
    - Các trường phụ mới mà AI bổ sung hợp lệ sẽ được nối vào cuối.
    """
    if isinstance(original, dict):
        if not isinstance(improved, dict):
            return original

        result = {}
        # 1. Duyệt qua tất cả các key của original THEO ĐÚNG THỨ TỰ GỐC
        for k, orig_v in original.items():
            if k in improved:
                imp_v = improved[k]
                if isinstance(orig_v, dict) and isinstance(imp_v, dict):
                    result[k] = preserve_and_reconcile_schema(orig_v, imp_v)
                elif isinstance(orig_v, list) and isinstance(imp_v, list):
                    result[k] = _reconcile_list(orig_v, imp_v)
                else:
                    if imp_v is not None and str(imp_v).strip() != "":
                        result[k] = imp_v
                    else:
                        result[k] = orig_v
            else:
                # Key bị AI bỏ quên -> KHÔI PHỤC NGUYÊN VẸN TỪ BẢN GỐC (TUYỆT ĐỐI KHÔNG BỊ XOÁ)
                result[k] = orig_v

        # 2. Bổ sung các key mới hợp lệ mà AI tạo thêm (nếu có) vào cuối
        for k, imp_v in improved.items():
            if k not in result:
                result[k] = imp_v

        return result

    elif isinstance(original, list):
        if not isinstance(improved, list):
            return original
        return _reconcile_list(original, improved)

    else:
        if improved is not None and str(improved).strip() != "":
            return improved
        return original


def _reconcile_list(orig_list: list, imp_list: list) -> list:
    """Xử lý danh sách các phần tử / panels / scenes."""
    if not orig_list:
        return imp_list

    if all(isinstance(x, dict) for x in orig_list):
        result = []
        for i, orig_item in enumerate(orig_list):
            if i < len(imp_list) and isinstance(imp_list[i], dict):
                result.append(preserve_and_reconcile_schema(orig_item, imp_list[i]))
            else:
                result.append(orig_item)

        if len(imp_list) > len(orig_list):
            result.extend(imp_list[len(orig_list):])
        return result
    else:
        return imp_list if len(imp_list) > 0 else orig_list


# =====================================================================
# Dynamic System Prompts (Tailored for Fixed Framework Preservation)
# =====================================================================

SYSTEM_PROMPT_JSON_PRESERVE = """BẠN LÀ MỘT CHUYÊN GIA NÂNG CẤP VÀ HOÀN THIỆN PROMPT AI HÀNG ĐẦU THẾ GIỚI (AI PROMPT ENGINEER & ART DIRECTOR).
NHIỆM VỤ: Nâng cấp, trau chuốt và làm giàu câu lệnh prompt AI dạng JSON theo đúng yêu cầu của người dùng.

QUY TẮC BẢO TOÀN BỘ KHUNG TUYỆT ĐỐI (CRITICAL FRAMEWORK PRESERVATION RULES):
1. GIỮ VỮNG NGUYÊN VẸN 100% BỘ KHUNG VÀ TẤT CẢ CÁC THUỘC TÍNH (PROPERTIES/KEYS):
   - Mỗi câu lệnh prompt gốc đã là một BỘ KHUNG CỐ ĐỊNH (fixed schema) hoàn chỉnh.
   - BẠN TUYỆT ĐỐI KHÔNG ĐƯỢC XOÁ BẤT KỲ THUỘC TÍNH NÀO, dù ở cấp gốc (root) hay các cấp lồng sâu (nested properties/arrays).
   - BẠN TUYỆT ĐỐI KHÔNG ĐƯỢC THAY ĐỔI VỊ TRÍ, THỨ TỰ xuất hiện của các thuộc tính trong JSON. Thứ tự các key trong `improved_prompt` PHẢI giống hệt 100% như prompt gốc.
   - BẠN TUYỆT ĐỐI KHÔNG ĐƯỢC tự ý đổi tên các thuộc tính, không được gom cụm hoặc thay thế bằng một cấu trúc schema mẫu nào khác.
2. CHỈ CẢI TIẾN VÀ LÀM GIÀU GIÁ TRỊ (VALUES):
   - Người dùng ở đây CHỈ CẢI TIẾN chứ KHÔNG XOÁ. Hãy nâng cấp các giá trị (values), thông số kỹ thuật, mô tả nghệ thuật, ánh sáng, góc máy, phục trang, biểu cảm, không khí bên trong các trường tương ứng theo yêu cầu.
   - Với bất kỳ trường nào không liên quan đến yêu cầu cải tiến, BẮT BUỘC GIỮ NGUYÊN 100% giá trị gốc, không làm rỗng, không xóa.
3. TIÊU ĐỀ:
   - Đặt tiêu đề ngắn gọn, bắt mắt, súc tích (4-10 từ) bằng 100% TIẾNG VIỆT tự nhiên.
4. ĐỊNH DẠNG ĐẦU RA (OUTPUT FORMAT):
   Chỉ trả về DUY NHẤT một JSON object hợp lệ, KHÔNG bọc trong markdown codeblock (không dùng ```json ... ```):
   {
     "title": "Tiêu đề tiếng Việt ngắn gọn, hấp dẫn cho câu lệnh đã cải tiến",
     "improved_prompt": {
       // CẤU TRÚC JSON CHÍNH XÁC 100% NHƯ PROMPT GỐC (GIỮ NGUYÊN TẤT CẢ CÁC KEYS VÀ THỨ TỰ, CHỈ CẢI TIẾN GIÁ TRỊ BÊN TRONG)
     },
     "explanation": "Lời giải thích chi tiết bằng tiếng Việt về những trường đã được nâng cấp và lý do cải tiến.",
     "changes": [
       {
         "area": "Tên thuộc tính/trường được sửa (ví dụ: lighting, camera, wardrobe...)",
         "before": "Nội dung hoặc tóm tắt cũ",
         "after": "Nội dung mới đã tối ưu",
         "reason": "Lý do cải tiến"
       }
     ]
   }
"""

SYSTEM_PROMPT_TEXT_PRESERVE = """BẠN LÀ MỘT CHUYÊN GIA NÂNG CẤP VÀ HOÀN THIỆN PROMPT AI HÀNG ĐẦU THẾ GIỚI (AI PROMPT ENGINEER & ART DIRECTOR).
NHIỆM VỤ: Nâng cấp, trau chuốt và làm giàu câu lệnh prompt AI dạng văn bản theo đúng yêu cầu của người dùng.

QUY TẮC BẢO TOÀN BỘ KHUNG TUYỆT ĐỐI (CRITICAL FRAMEWORK PRESERVATION RULES):
1. GIỮ VỮNG NGUYÊN VẸN 100% BỘ KHUNG, TIÊU ĐỀ MỤC VÀ BỐ CỤC:
   - Mỗi câu lệnh prompt gốc đã là một BỘ KHUNG CỐ ĐỊNH (fixed template).
   - Nếu prompt có các phân cảnh, tiêu đề mục, nhãn thuộc tính (ví dụ: "Cảnh 1:", "Trạng thái âm thanh:", "Prompt biểu cảm:"), BẠN TUYỆT ĐỐI KHÔNG ĐƯỢC XOÁ bất kỳ mục nào.
   - BẠN TUYỆT ĐỐI KHÔNG ĐƯỢC THAY ĐỔI VỊ TRÍ, THỨ TỰ các mục. Thứ tự xuất hiện từ đầu đến cuối phải được giữ nguyên vẹn 100%.
2. CHỈ CẢI TIẾN VÀ LÀM GIÀU NỘI DUNG:
   - Nâng cấp câu từ, miêu tả chi tiết, ánh sáng, phục trang, góc máy, kỹ xảo bên trong từng mục theo yêu cầu cải tiến.
   - Các mục không liên quan đến yêu cầu cải tiến phải được giữ nguyên.
3. TIÊU ĐỀ:
   - Đặt tiêu đề ngắn gọn, bắt mắt, súc tích (4-10 từ) bằng 100% TIẾNG VIỆT tự nhiên.
4. ĐỊNH DẠNG ĐẦU RA (OUTPUT FORMAT):
   Chỉ trả về DUY NHẤT một JSON object hợp lệ, KHÔNG bọc trong markdown codeblock:
   {
     "title": "Tiêu đề tiếng Việt ngắn gọn, hấp dẫn cho câu lệnh đã cải tiến",
     "improved_prompt": "Toàn bộ văn bản prompt đã nâng cấp, bảo toàn 100% các tiêu đề mục và thứ tự gốc",
     "explanation": "Lời giải thích chi tiết bằng tiếng Việt về những nội dung đã được nâng cấp và lý do cải tiến.",
     "changes": [
       {
         "area": "Tên phân đoạn hoặc thuộc tính được sửa",
         "before": "Nội dung cũ",
         "after": "Nội dung mới đã tối ưu",
         "reason": "Lý do cải tiến"
       }
     ]
   }
"""


def call_gemini_improve_prompt(system_prompt: str, user_content: str, cfg: Dict[str, Any]) -> Tuple[bool, Any, str]:
    api_key = cfg.get("gemini_api_key", "").strip()
    if not api_key:
        return False, None, "Chưa cấu hình GEMINI_API_KEY trong tệp .env. Vui lòng kiểm tra lại tệp .env."

    model_name = cfg.get("gemini_chat_model", "gemini-2.0-flash") or "gemini-2.0-flash"
    timeout = cfg.get("timeout", 300)
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

    payload = {
        "system_instruction": {
            "parts": [{"text": system_prompt}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_content}]
            }
        ],
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
                return False, None, "Google Gemini không trả về kết quả nào."

            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                return False, None, "Google Gemini phản hồi rỗng."

            raw_text_out = parts[0].get("text", "").strip()
            cleaned = clean_json_response(raw_text_out)
            parsed_json = json.loads(cleaned)
            return True, parsed_json, f"Cải tiến thành công qua Google Gemini ({model_name})"
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        return False, None, f"Lỗi HTTP {e.code} từ Google Gemini API: {err_msg[:300]}"
    except Exception as e:
        return False, None, f"Lỗi kết nối tới Google Gemini: {str(e)}"


def call_openai_improve_prompt(system_prompt: str, user_content: str, cfg: Dict[str, Any]) -> Tuple[bool, Any, str]:
    api_key = cfg.get("api_key", "").strip()
    base_url = cfg.get("base_url", "https://api.openai.com/v1").strip()
    model_name = cfg.get("chat_model") or cfg.get("model_name") or "gpt-4o-mini"
    timeout = cfg.get("timeout", 300)
    use_stream = cfg.get("stream", True)

    if not api_key:
        return False, None, "Chưa cấu hình AI_API_KEY trong tệp .env. Vui lòng kiểm tra lại tệp .env."

    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        "temperature": 0.2,
        "stream": use_stream
    }

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        req = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            if use_stream:
                chunks = []
                for raw_line in resp:
                    line = raw_line.decode("utf-8", errors="ignore").strip()
                    if not line or line.startswith(":"):
                        continue
                    if line.startswith("data:"):
                        chunk_data = line[5:].strip()
                        if chunk_data == "[DONE]":
                            break
                        try:
                            chunk_obj = json.loads(chunk_data)
                            choices = chunk_obj.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content_piece = delta.get("content") or delta.get("text") or ""
                                if content_piece:
                                    chunks.append(content_piece)
                                else:
                                    msg = choices[0].get("message", {})
                                    if msg.get("content"):
                                        chunks.append(msg["content"])
                        except Exception:
                            continue
                raw_response = "".join(chunks).strip()
            else:
                body = resp.read().decode("utf-8", errors="ignore")
                raw_response = parse_chat_response(body).strip()

            if not raw_response:
                return False, None, "Mô hình AI không trả về nội dung nào."

            cleaned_content = clean_json_response(raw_response)

            try:
                parsed_json = json.loads(cleaned_content)
            except json.JSONDecodeError:
                fixed_content = re.sub(r",\s*([\]}])", r"\1", cleaned_content)
                parsed_json = json.loads(fixed_content)

            if not isinstance(parsed_json, dict):
                return False, None, f"Dữ liệu trả về không phải là JSON object hợp lệ: {raw_response[:200]}"

            return True, parsed_json, "Thành công"

    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        return False, None, f"Lỗi HTTP {e.code} từ nhà cung cấp AI: {err_msg[:300]}"
    except (urllib.error.URLError, TimeoutError) as e:
        err_str = str(e)
        if "timed out" in err_str.lower() or isinstance(e, TimeoutError):
            return False, None, f"Quá thời gian chờ (Timeout {timeout}s) khi kết nối tới AI. Vui lòng thử lại."
        return False, None, f"Lỗi kết nối tới nhà cung cấp AI: {err_str}"
    except Exception as e:
        return False, None, f"Lỗi xử lý gọi AI: {str(e)}"


# =====================================================================
# Main AI Prompt Improver Service
# =====================================================================

def call_ai_improve_prompt(
    original_prompt: str,
    instructions: str,
    provider: Optional[str] = None,
    original_parsed_json: Optional[Any] = None,
    original_prompt_type: Optional[str] = None,
    original_title: Optional[str] = None
) -> Tuple[bool, Dict[str, Any], str]:
    """
    Cải tiến prompt tuân thủ nghiêm ngặt việc giữ vững tất cả các thuộc tính và vị trí của khung gốc.
    """
    cfg = get_ai_config()
    active_provider = (provider or cfg.get("provider") or "openai").lower()

    # 1. Xác định cấu trúc gốc (JSON hay Text)
    target_parsed_json = original_parsed_json
    if target_parsed_json is None and isinstance(original_prompt, str):
        s = original_prompt.find('{')
        e = original_prompt.rfind('}')
        if s != -1 and e != -1 and e > s:
            try:
                target_parsed_json = json.loads(original_prompt[s:e+1])
            except Exception:
                target_parsed_json = None

    is_json = target_parsed_json is not None and isinstance(target_parsed_json, (dict, list))

    # 2. Xây dựng System Prompt & User Content phù hợp
    if is_json:
        system_prompt = SYSTEM_PROMPT_JSON_PRESERVE
        json_repr = json.dumps(target_parsed_json, indent=2, ensure_ascii=False)
        user_content = (
            "--- CÂU LỆNH PROMPT GỐC (BỘ KHUNG CỐ ĐỊNH) ---\n"
            f"{json_repr}\n\n"
            "--- YÊU CẦU CẢI TIẾN CỦA NGƯỜI DÙNG ---\n"
            f"{instructions}\n\n"
            "LƯU Ý BẮT BUỘC: Bạn phải giữ NGUYÊN VẸN 100% tất cả các thuộc tính (keys) và THỨ TỰ của khung JSON gốc ở trên. "
            "Tuyệt đối KHÔNG XOÁ bất kỳ trường nào, không đổi vị trí các trường, chỉ nâng cấp giá trị các trường theo yêu cầu cải tiến."
        )
    else:
        system_prompt = SYSTEM_PROMPT_TEXT_PRESERVE
        user_content = (
            "--- CÂU LỆNH PROMPT GỐC (BỘ KHUNG CỐ ĐỊNH) ---\n"
            f"{original_prompt}\n\n"
            "--- YÊU CẦU CẢI TIẾN CỦA NGƯỜI DÙNG ---\n"
            f"{instructions}\n\n"
            "LƯU Ý BẮT BUỘC: Bạn phải giữ NGUYÊN VẸN 100% bố cục, các tiêu đề mục, phân cảnh và THỨ TỰ của khung prompt gốc ở trên. "
            "Tuyệt đối KHÔNG XOÁ bất kỳ mục nào, không đổi vị trí các mục, chỉ nâng cấp nội dung theo yêu cầu cải tiến."
        )

    # 3. Gửi yêu cầu tới Provider AI
    if active_provider == "gemini":
        success, raw_result, msg = call_gemini_improve_prompt(system_prompt, user_content, cfg)
    else:
        success, raw_result, msg = call_openai_improve_prompt(system_prompt, user_content, cfg)

    if not success:
        return False, {}, msg

    if not isinstance(raw_result, dict):
        return False, {}, "Định dạng kết quả trả về từ AI không phải là đối tượng JSON."

    # 4. Trích xuất và chuẩn hóa tiêu đề
    title = raw_result.get("title") or original_title or "Prompt đã cải tiến"
    title = re.sub(r"^[\"'\s*`]+|[\"'\s*`]+$", "", title)
    title = re.sub(r"^(?:tiêu đề|title)\s*:\s*", "", title, flags=re.IGNORECASE).strip()
    title = re.sub(r"^[\"'\s*`]+|[\"'\s*`]+$", "", title)
    if not title:
        title = original_title or "Prompt đã cải tiến"

    explanation = raw_result.get("explanation", "Đã nâng cấp câu lệnh theo yêu cầu và bảo toàn 100% bộ khung gốc.")
    changes = raw_result.get("changes", [])
    if not isinstance(changes, list):
        changes = []

    improved_val = raw_result.get("improved_prompt")
    if improved_val is None:
        improved_val = raw_result

    # 5. Áp dụng quy tắc bảo toàn cấu trúc nghiêm ngặt (Framework Preservation Guarantee)
    parsed_json = None
    prompt_type = "text"
    prompt_code = ""

    if is_json:
        prompt_type = "json"
        if isinstance(improved_val, str):
            s = improved_val.find('{')
            e = improved_val.rfind('}')
            if s != -1 and e != -1 and e > s:
                try:
                    improved_val = json.loads(improved_val[s:e+1])
                except Exception:
                    pass

        # Thực thi hàm đối chiếu và bảo toàn 100% thuộc tính + thứ tự từ bản gốc
        if isinstance(improved_val, (dict, list)):
            reconciled = preserve_and_reconcile_schema(target_parsed_json, improved_val)
        else:
            reconciled = target_parsed_json

        parsed_json = reconciled
        prompt_code = json.dumps(reconciled, indent=2, ensure_ascii=False)
        fields = extract_flat_fields(reconciled)

    else:
        prompt_type = "text"
        if isinstance(improved_val, (dict, list)):
            prompt_code = json.dumps(improved_val, indent=2, ensure_ascii=False)
        else:
            prompt_code = str(improved_val).strip()

        fields = [
            {"path": "title", "key": "title", "label": "Tiêu đề", "value": title, "type": "text", "is_list": False},
            {"path": "prompt_content", "key": "prompt_content", "label": "Nội dung câu lệnh", "value": prompt_code, "type": "textarea", "is_list": False}
        ]

    result = {
        "title": title,
        "prompt_type": prompt_type,
        "prompt_code": prompt_code,
        "parsed_json": parsed_json,
        "fields": fields,
        "explanation": explanation,
        "changes": changes
    }

    return True, result, "Cải tiến prompt thành công (Đã bảo toàn trọn vẹn bộ khung thuộc tính gốc)"
