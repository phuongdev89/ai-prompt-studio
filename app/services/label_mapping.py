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
    "role": "Vai trò"
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
# Định nghĩa: Các trường người dùng cần truyền nội dung vào hoặc chọn giá trị
# ==========================================

import re

PRIMARY_INPUT_CHOICE_KEYS = {
    # Nhóm nhập liệu / tuỳ biến nội dung (User inputs)
    "topic", "product", "product_name", "brand", "target_audience", "audience", "niche",
    "hook", "hook_first_3s", "pain_point", "problem", "solution", "solution_product",
    "cta", "call_to_action", "tone", "tone_of_voice", "voice", "keywords", "key_benefits",
    "subject", "character", "description", "outfit", "wardrobe", "clothing", "top", "bottoms",
    "pose", "expression", "environment", "location", "setting", "background",
    # Nhóm lựa chọn giá trị (User choices / options)
    "aspect_ratio", "ratio", "camera_angle", "angle", "shot_type", "lighting", "style",
    "aesthetic", "mood", "genre", "platform", "target_platform", "format", "content_format",
    "duration", "duration_seconds", "layout", "composition", "pacing", "color", "colors"
}

SECONDARY_DETAIL_KEYS = {
    "hair", "eyes", "face", "skin", "makeup", "accessories", "color_palette", "atmosphere",
    "lens", "framing", "perspective", "action", "headline", "caption", "vietnamese_caption"
}

EXCLUDED_OR_TECHNICAL_KEYS = {
    "instructions", "reference_instructions", "anti_patterns", "negative_prompt",
    "reference_file", "render_engine", "rendering_parameters", "version", "iso",
    "shutter_speed", "focal_length", "sensor", "sensor_size", "print_readiness",
    "generation_profile", "id", "panel_id", "prompt_id", "original_index", "constraints",
    "expected_output", "schema", "output_format", "panel_format", "grid_structure_panels"
}

def detect_primary_fields(fields: list, category: str = "image", min_primary: int = 3, max_primary: int = 8) -> list:
    """
    Tự động chấm điểm và đánh dấu `is_primary = True` cho các thuộc tính cốt lõi của Prompt:
    - Những trường người sử dụng cần truyền nội dung vào (topic, product, target_audience, outfit, pose...)
    - Những trường cần lựa chọn giá trị (aspect_ratio, camera_angle, style, lighting, platform...)
    - Các trường chứa biến placeholder mẫu: [nhập ...], <chủ đề>, {từ khóa}
    """
    if not fields:
        return fields

    scored_fields = []
    for idx, f in enumerate(fields):
        key = (f.get("key") or "").strip().lower()
        path = (f.get("path") or "").strip().lower()
        leaf = path.split(".")[-1] if "." in path else key
        val = str(f.get("value") or "").strip()
        val_lower = val.lower()

        score = 0
        depth = path.count(".")

        # 1. Các trường nằm trong nhóm biến đầu vào tường minh (input_parameters, dynamic_input_variables, v.v.)
        if any(p in path for p in ["input_parameters", "dynamic_input_variables", "user_inputs", "parameters", "variables"]):
            score += 35

        # 2. Giá trị chứa placeholder cần người dùng truyền nội dung vào (vd: [tên sản phẩm], <topic>, {chủ đề})
        if re.search(r'\[.+?\]|<.+?>|\{.+?\}', val):
            score += 30
        if any(kw in val_lower for kw in ["nhập ", "chọn ", "tùy chọn", "điền ", "ví dụ:"]):
            score += 15

        # 3. Thuộc tính chính người dùng cần nhập hoặc chọn giá trị
        if leaf in PRIMARY_INPUT_CHOICE_KEYS or key in PRIMARY_INPUT_CHOICE_KEYS:
            score += 25
        elif any(k in leaf for k in ["product", "topic", "hook", "target", "tone", "style", "outfit", "cloth", "pose", "light", "camera", "aspect"]):
            score += 15
        elif leaf in SECONDARY_DETAIL_KEYS or key in SECONDARY_DETAIL_KEYS:
            score += 10

        # 4. Trừ điểm các trường kỹ thuật / cố định không cần người dùng can thiệp
        if leaf in EXCLUDED_OR_TECHNICAL_KEYS or key in EXCLUDED_OR_TECHNICAL_KEYS:
            score -= 35
        if "instructions" in leaf or "instructions" in path:
            score -= 30
        if "reference" in leaf:
            score -= 20

        # 5. Phạt nặng các phân cảnh phụ trong storyboard (panel_2, panel_3, ... panel_25)
        panel_match = re.search(r'panel_(\d+)', path)
        if panel_match:
            p_num = int(panel_match.group(1))
            if p_num > 1:
                score -= 30
            else:
                score -= 5

        # 6. Độ sâu đường dẫn: ưu tiên trường nông (top-level)
        if depth <= 2:
            score += 8
        elif depth >= 4:
            score -= 8

        # 7. Giá trị có nội dung thực chất
        if len(val) >= 10:
            score += 3
        elif len(val) == 0:
            score -= 5

        scored_fields.append((score, idx, f))

    # Sắp xếp điểm giảm dần
    scored_fields.sort(key=lambda x: (x[0], -x[1]), reverse=True)

    selected_indices = set()
    for score, idx, f in scored_fields:
        if score >= 15 and len(selected_indices) < max_primary:
            selected_indices.add(idx)

    # Đảm bảo tối thiểu min_primary nếu có trường điểm dương
    if len(selected_indices) < min_primary:
        for score, idx, f in scored_fields:
            if idx not in selected_indices and score > 0:
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

