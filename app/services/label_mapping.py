"""
Module quản lý tập trung Mapping nhãn (Label Mapping) cho các trường tham số của Prompt.
Cung cấp từ điển chuẩn hóa và hàm format_field_label có thể tái sử dụng trên toàn hệ thống.
"""

from typing import Dict, Optional

# Bản đồ ánh xạ nhãn hiển thị tiếng Việt / Song ngữ cho các trường tham số phổ biến
LABEL_MAPPING: Dict[str, str] = {
    # Nhóm Bố cục, Bối cảnh & Không gian
    "layout": "Bố cục / Layout",
    "poses_grid": "Lưới tư thế / Poses Grid",
    "environment": "Môi trường & Không gian / Environment",
    "foreground_element": "Tiền cảnh / Foreground",
    "background": "Bối cảnh / Background",
    "setting": "Không gian / Setting",
    "atmosphere": "Bầu không khí / Atmosphere",
    "lighting": "Ánh sáng / Lighting",

    # Nhóm Nhân vật & Giải phẫu
    "subject_identity_lock": "Khóa nhận diện / Identity Lock",
    "anatomy_and_textures": "Giải phẫu & Bề mặt / Anatomy & Textures",
    "skin": "Làn da / Skin",
    "lips": "Đôi môi / Lips",
    "eyes": "Đôi mắt / Eyes",
    "hair": "Kiểu tóc / Hair",
    "face": "Gương mặt / Face",
    "clothing": "Trang phục / Clothing",
    "outfit": "Trang phục / Outfit",
    "wardrobe": "Trang phục & Phụ kiện / Wardrobe",
    "pose": "Tư thế / Pose",
    "expression": "Biểu cảm / Expression",
    "gender": "Giới tính / Gender",
    "age": "Độ tuổi / Age",

    # Nhóm Camera & Thông số kỹ thuật
    "camera": "Máy ảnh / Camera",
    "camera_settings": "Thông số máy ảnh / Camera Specs",
    "lens": "Ống kính / Lens",
    "focus": "Tiêu cự / Focus",
    "resolution": "Độ phân giải / Resolution",
    "aspect_ratio": "Tỉ lệ / Aspect Ratio",
    "orientation": "Hướng khung hình / Orientation",
    "quality": "Chất lượng / Quality",
    "quality_specs": "Chất lượng / Quality Specs",
    "mandatory_output_criteria": "Tiêu chí kết quả / Mandatory Criteria",

    # Nhóm Phong cách & Thẩm mỹ
    "style": "Phong cách / Style",
    "aesthetic": "Thẩm mỹ / Aesthetic",
    "mood": "Tâm trạng / Mood",
    "energy": "Năng lượng / Energy",
    "genre": "Thể loại / Genre",
    "description": "Mô tả / Description",
    "negative_prompt": "Prompt phủ định / Negative Prompt",

    # Nhóm Nội dung & Dự án
    "title": "Tiêu đề / Title",
    "prompt_content": "Nội dung câu lệnh / Prompt Content",
    "instructions": "Hướng dẫn / Instructions",
    "language": "Ngôn ngữ / Language",
    "primary_language": "Ngôn ngữ chính / Primary Language",
}

def format_field_label(field_key_or_path: str, full_path: str = "") -> str:
    """
    Chuẩn hóa và lấy nhãn hiển thị cho trường tham số:
    1. Nếu là đường dẫn phân cấp (vd: 'project_metadata.target_platform'), lấy tên trường con cuối cùng ('target_platform').
    2. Nếu trường con đó (hoặc full_path) có trong LABEL_MAPPING -> lấy từ mapping.
    3. Nếu chưa có trong mapping -> định dạng tự nhiên từ chính tên trường:
       - Thay thế '_' và '-' thành khoảng trắng
       - Viết hoa chữ cái đầu tiên (vd: 'target_platform' -> 'Target platform')
    """
    if not field_key_or_path:
        return ""

    raw_str = str(field_key_or_path).strip()
    path_to_check = str(full_path).strip() if full_path else raw_str

    # Trích xuất trường con (leaf key) nếu là đường dẫn chấm (vd: 'a.b.c' -> 'c')
    if "." in raw_str:
        leaf_key = raw_str.split(".")[-1].strip()
    elif "." in path_to_check:
        leaf_key = path_to_check.split(".")[-1].strip()
    else:
        leaf_key = raw_str

    leaf_lower = leaf_key.lower()
    path_lower = path_to_check.lower()

    # 1. Kiểm tra exact match theo tên trường con trong LABEL_MAPPING
    if leaf_lower in LABEL_MAPPING:
        return LABEL_MAPPING[leaf_lower]

    # 2. Kiểm tra exact match theo full_path trong LABEL_MAPPING
    if path_lower in LABEL_MAPPING:
        return LABEL_MAPPING[path_lower]

    # 3. Nếu chưa có trong mapping -> Định dạng hiển thị trực tiếp từ tên trường
    # Thay _ và - thành dấu cách
    clean_name = leaf_key.replace("_", " ").replace("-", " ").strip()
    if not clean_name:
        return leaf_key

    if clean_name.isupper():
        clean_name = clean_name.lower()

    # Viết hoa chữ cái đầu tiên, giữ nguyên phần còn lại (vd: 'Target platform')
    return clean_name[0].upper() + clean_name[1:]

# Alias tương thích ngược với code cũ
format_label = format_field_label

# ==========================================
# Tự Động Phát Hiện Thuộc Tính Chính (Primary Attributes)
# ==========================================

PRIMARY_HIGH_PRIORITY_KEYS = {
    # Nhóm Nhân vật / Visual
    "description", "subject", "subject_identity_lock", "wardrobe", "clothing", "outfit",
    "pose", "style", "lighting", "layout", "aspect_ratio",
    # Nhóm Content & Script
    "topic", "hook", "product", "product_name", "target_audience", "problem", "solution",
    "cta", "target_platform"
}

PRIMARY_MEDIUM_PRIORITY_KEYS = {
    # Nhóm Nhân vật / Visual
    "face", "hair", "eyes", "expression", "action", "environment", "setting", "background",
    "camera", "camera_angle", "lens", "aesthetic", "mood", "atmosphere", "genre", "composition",
    # Nhóm Content & Script
    "audience", "niche", "platform", "framework", "tone", "pacing", "content_format", "content_type"
}

TECHNICAL_LOW_PRIORITY_KEYS = {
    "version", "render_engine", "rendering_parameters", "iso", "shutter_speed",
    "focal_length", "aperture", "color_temperature", "anti_patterns", "instructions",
    "reference_instructions", "max_seconds", "min_seconds", "duration_seconds",
    "print_readiness", "generation_profile"
}

def detect_primary_fields(fields: list, category: str = "character", min_primary: int = 3, max_primary: int = 7) -> list:
    """
    Tự động chấm điểm và đánh dấu `is_primary = True` cho các thuộc tính cốt lõi của Prompt
    khi chuyển đổi từ văn bản thô sang JSON.
    Đảm bảo sau khi chuyển đổi JSON luôn có từ min_primary đến max_primary thuộc tính chính phù hợp.
    """
    if not fields:
        return fields

    scored_fields = []
    for idx, f in enumerate(fields):
        key = (f.get("key") or "").strip().lower()
        path = (f.get("path") or "").strip().lower()
        leaf = path.split(".")[-1] if "." in path else key
        val = str(f.get("value") or "").strip()

        score = 0
        depth = path.count(".")

        # Điểm ưu tiên từ khoá cốt lõi
        if leaf in PRIMARY_HIGH_PRIORITY_KEYS or key in PRIMARY_HIGH_PRIORITY_KEYS:
            score += 20
        elif leaf in PRIMARY_MEDIUM_PRIORITY_KEYS or key in PRIMARY_MEDIUM_PRIORITY_KEYS:
            score += 12
        elif any(k in leaf for k in ["desc", "style", "light", "pose", "cloth", "scene", "hook", "target"]):
            score += 8

        # Trừ điểm trường kỹ thuật hoặc sâu
        if leaf in TECHNICAL_LOW_PRIORITY_KEYS or key in TECHNICAL_LOW_PRIORITY_KEYS:
            score -= 15

        if "panel_" in path:
            if "panel_1" in path:
                score += 2
            else:
                score -= 10

        if depth <= 2:
            score += 5
        elif depth >= 4:
            score -= 5

        # Giá trị có nội dung mô tả
        if len(val) >= 15:
            score += 3
        elif len(val) == 0:
            score -= 5

        scored_fields.append((score, idx, f))

    # Sắp xếp theo điểm giảm dần
    scored_fields.sort(key=lambda x: (x[0], -x[1]), reverse=True)

    # Chọn các trường có điểm cao >= 10, tối đa max_primary
    selected_indices = set()
    for score, idx, f in scored_fields:
        if score >= 10 and len(selected_indices) < max_primary:
            selected_indices.add(idx)

    # Nếu chưa đủ min_primary, lấy thêm các trường có điểm cao nhất
    if len(selected_indices) < min_primary:
        for score, idx, f in scored_fields:
            if idx not in selected_indices and score >= 0:
                selected_indices.add(idx)
                if len(selected_indices) >= min_primary:
                    break

    # Nếu vẫn chưa đủ (ví dụ toàn trường điểm thấp), lấy top min_primary trường đầu
    if len(selected_indices) < min(min_primary, len(fields)):
        for score, idx, f in scored_fields:
            if idx not in selected_indices:
                selected_indices.add(idx)
                if len(selected_indices) >= min(min_primary, len(fields)):
                    break

    # Gán cờ is_primary vào danh sách
    for idx, f in enumerate(fields):
        f["is_primary"] = bool(idx in selected_indices)

    return fields

